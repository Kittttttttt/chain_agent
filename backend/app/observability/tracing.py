"""LangSmith 观测性接入。

职责：
1. `setup_langsmith()` 将 .env / Settings 中的 LangSmith 配置注入 os.environ
   （LangGraph 与 langsmith 客户端均从环境变量读取，需在首次调用前完成）。
2. `traceable()` 装饰器包装 Agent 关键方法，在 LangSmith 中生成可观测 span。
3. 未安装 langsmith 或追踪关闭时优雅降级：装饰器退化为直通，不影响业务。
4. numpy 兼容层：langsmith 序列化默认开启 orjson 的 OPT_SERIALIZE_NUMPY，
   会触发 orjson 内部 `import numpy`；在 numpy 导入即崩溃的环境中（如
   Python 3.14 + numpy 2.4.x），剥离该选项以保证 tracing 可用。

注意：pydantic-settings 只把 .env 读入字段，不会导出到 os.environ，
因此必须显式调用 setup_langsmith() 设置 LANGSMITH_API_KEY 等变量。
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from typing import Any, Callable

from loguru import logger

try:  # pragma: no cover - 取决于环境
    from langsmith import traceable as _langsmith_traceable

    _LANGSMITH_AVAILABLE = True
except Exception:  # noqa: BLE001
    _langsmith_traceable = None  # type: ignore[assignment]
    _LANGSMITH_AVAILABLE = False

_configured = False
_numpy_probed = False
_numpy_broken = False


def setup_langsmith(settings: Any) -> None:
    """根据配置启用/关闭 LangSmith 追踪。在应用启动、图编译前调用一次即可。"""
    global _configured
    if _configured:
        return
    _configured = True

    enabled = bool(getattr(settings, "trace_enabled", True)) and bool(
        getattr(settings, "langsmith_tracing", True)
    )
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"

    if enabled:
        api_key = getattr(settings, "langsmith_api_key", "") or os.environ.get(
            "LANGSMITH_API_KEY", ""
        )
        if api_key:
            os.environ["LANGSMITH_API_KEY"] = api_key
        project = getattr(settings, "langsmith_project", "") or os.environ.get(
            "LANGSMITH_PROJECT", ""
        )
        if project:
            os.environ["LANGSMITH_PROJECT"] = project
        if _numpy_import_is_broken():
            _install_numpy_free_serde()

    status = "enabled" if enabled else "disabled"
    logger.info("LangSmith tracing {} (langsmith 包: {})", status, _LANGSMITH_AVAILABLE)


# ---------------------------------------------------------------------------
# numpy 兼容层
# ---------------------------------------------------------------------------


def _numpy_import_is_broken() -> bool:
    """探测 numpy 导入是否安全。

    numpy 在部分环境（如 Python 3.14 + numpy 2.4.x）导入时触发 BLAS 自检，
    进程直接崩溃（STATUS_STACK_BUFFER_OVERRUN，0xC0000409），try/except 无法捕获，
    因此必须用子进程探测。结果缓存，仅探测一次。
    """
    global _numpy_probed, _numpy_broken
    if _numpy_probed:
        return _numpy_broken
    _numpy_probed = True

    if importlib.util.find_spec("numpy") is None:
        return False  # 未安装 numpy，无需兼容

    try:
        proc = subprocess.run(
            [sys.executable, "-c", "import numpy"],
            capture_output=True,
            timeout=30,
            check=False,
        )
        _numpy_broken = proc.returncode != 0
    except Exception:  # noqa: BLE001 - 子进程探测失败时按「有风险」处理
        logger.warning("numpy 探测失败，默认安装 LangSmith serde 兼容补丁")
        _numpy_broken = True
    return _numpy_broken


def _install_numpy_free_serde() -> None:
    """剥离 langsmith 序列化中的 OPT_SERIALIZE_NUMPY。

    langsmith 对 trace 的 inputs/outputs 序列化时给 orjson 传 OPT_SERIALIZE_NUMPY，
    orjson 会在调用时内部 `import numpy`，在本环境直接崩溃。项目 trace 数据中
    不包含 numpy 数组，去掉该选项行为等价，仅影响极端情况下 numpy 数组的表示。
    """
    import json

    import orjson

    try:
        from langsmith._internal import _operations as ls_ops
        from langsmith._internal import _serde as ls_serde
    except Exception:  # noqa: BLE001 - 版本差异导致内部结构变化时放弃补丁
        logger.warning("langsmith 内部结构不匹配，跳过 serde 兼容补丁")
        return

    _orig_dumps = ls_serde.dumps_json

    def _dumps_no_numpy(obj: Any) -> bytes:
        try:
            return orjson.dumps(
                obj,
                default=ls_serde._serialize_json,
                option=orjson.OPT_SERIALIZE_DATACLASS
                | orjson.OPT_SERIALIZE_UUID
                | orjson.OPT_NON_STR_KEYS,
            )
        except TypeError:
            # 与原实现一致的兜底路径（json.dumps，不涉及 numpy）
            return json.dumps(obj, default=ls_serde._serialize_json, ensure_ascii=True).encode("utf-8")
        except Exception:  # noqa: BLE001
            return _orig_dumps(obj)

    ls_serde.dumps_json = _dumps_no_numpy
    ls_ops._dumps_json = _dumps_no_numpy  # _operations 直接绑定了 dumps_json
    logger.info("已安装 LangSmith serde 兼容补丁（numpy 不可用，剥离 numpy 序列化）")


def _to_jsonable(obj: Any) -> Any:
    """将任意对象转换为可 JSON 序列化的结构（用于 span 的 inputs/outputs）。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        try:
            return _to_jsonable(dump(mode="json"))
        except Exception:  # noqa: BLE001
            try:
                return _to_jsonable(dump())
            except Exception:  # noqa: BLE001
                return str(obj)
    return str(obj)


def _sanitize_inputs(inputs: dict) -> dict:
    """清洗 traceable 的入参。

    langsmith 的 process_inputs 契约是 Callable[[dict], dict]：
    接收完整的 inputs dict，返回清洗后的 dict。
    """
    return {k: _to_jsonable(v) for k, v in inputs.items()}


def traceable(name: str | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """LangSmith traceable 包装器：未安装 / 关闭时直通原函数，避免引入运行时依赖。"""

    def passthrough(func: Callable[..., Any]) -> Callable[..., Any]:
        return func

    if not _LANGSMITH_AVAILABLE:
        return passthrough

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        return _langsmith_traceable(
            name=name or f"{func.__module__}.{func.__qualname__}",
            process_inputs=_sanitize_inputs,
            process_outputs=_to_jsonable,
        )(func)

    return decorator
