"""契约层：内容契约 · 平台能力模型 · 发布清单。

这一层**不认识任何具体平台**。它读 ``publish/capabilities/<platform>.toml``，
产出 manifest JSON，再把 TOML 与 manifest 交给平台 adapter。
平台 adapter 也**不 import 这一层**——两边唯一的接缝是那份 TOML 与那份
manifest JSON（``publish/spec/00-架构设计.md`` §5、§6、§11.1）。

所以：本包里任何一行都**不许** import ``toutiao.*`` / ``wechat.*`` / ``bilibili.*``。

对外只抛 ``PublishKitError`` 这一族异常：调用方一句
``except PublishKitError`` 就能兜住，而 KeyError / TypeError / 内建
ValueError 不会从这一层漏出去。
"""


class PublishKitError(Exception):
    """契约层所有「有意抛出的」错误的基类。"""


# 下面这些 import 依赖上面刚定义好的 PublishKitError（子模块用
# ``from . import PublishKitError`` 取它），所以它们必须排在类定义之后。
from .capability import (  # noqa: E402
    AUTOMATIONS,
    KINDS,
    PLATFORM_ID_RE,
    REVIEWS,
    Capability,
    CapabilityError,
    CapabilityFieldError,
    CapabilityFileError,
    available_platforms,
    default_capabilities_dir,
    list_capabilities,
    load_capability,
    load_capability_file,
)
from .contract import (  # noqa: E402
    CONTENT_KINDS,
    PASSTHROUGH_FIELDS,
    REPRINT_POLICIES,
    ContentContract,
    ContractError,
    ContractFieldError,
    ContractFileError,
    contract_from_fields,
    parse_front_matter,
    read_contract,
    validate_fields,
)
from .manifest import (  # noqa: E402
    Manifest,
    ManifestError,
    ManifestFieldError,
    validate_manifest,
)

__all__ = [
    "AUTOMATIONS",
    "CONTENT_KINDS",
    "KINDS",
    "PASSTHROUGH_FIELDS",
    "PLATFORM_ID_RE",
    "REVIEWS",
    "REPRINT_POLICIES",
    "Capability",
    "CapabilityError",
    "CapabilityFieldError",
    "CapabilityFileError",
    "ContentContract",
    "ContractError",
    "ContractFieldError",
    "ContractFileError",
    "Manifest",
    "ManifestError",
    "ManifestFieldError",
    "PublishKitError",
    "available_platforms",
    "contract_from_fields",
    "default_capabilities_dir",
    "list_capabilities",
    "load_capability",
    "load_capability_file",
    "parse_front_matter",
    "read_contract",
    "validate_fields",
    "validate_manifest",
]
