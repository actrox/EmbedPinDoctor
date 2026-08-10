from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict

# --- 基础数据模型 ---
class PinInfo(BaseModel):
    name: str
    functions: List[str]
    tags: List[str] = []
    timer: Optional[str] = None
    adc_channel: Optional[str] = None
    note: Optional[str] = None
    max_output_current_ma: Optional[float] = None
    absolute_max_input_voltage: Optional[float] = None

class ChipInfo(BaseModel):
    schema_version: int = 1
    id: str
    name: str
    voltage: str = "3.3V"
    io_voltage: float = 3.3
    absolute_max_input_voltage: float = 3.6
    default_max_output_current_ma: float = 8.0
    supports_open_drain: bool = True
    pins: List[PinInfo] = []
    data_status: str = "review_required"
    verified: bool = False
    confidence: str = "medium"
    source: Optional[str] = None
    datasheet_url: Optional[str] = None
    verified_at: Optional[str] = None
    verified_by: Optional[str] = None

class ModuleRequirement(BaseModel):
    module_pin: str
    function: str
    direction: str = "bidirectional"
    preferred_functions: List[str] = []
    requires_five_v_tolerant: Optional[bool] = None
    requires_open_drain: Optional[bool] = None
    drive_current_ma: Optional[float] = None
    pwm_frequency_hz: Optional[int] = None
    share_bus: Optional[bool] = None
    bus_key: Optional[str] = None
    note: Optional[str] = None

class ModuleInfo(BaseModel):
    schema_version: int = 1
    id: str
    name: str
    description: str = ""
    voltage: Optional[str] = None
    logic_voltage: Optional[float] = None
    voltage_tolerant: bool = False
    needs_pullup: bool = False
    pullup_voltage: Optional[float] = None
    i2c_bus: Optional[str] = None
    i2c_address: Optional[str] = None
    spi_bus: Optional[str] = None
    spi_mode: Optional[int] = None
    spi_max_hz: Optional[int] = None
    uart_requires_flow_control: bool = False
    source: Optional[str] = None
    requirements: List[ModuleRequirement] = []

# --- 分配与风险 ---
class AllocationItem(BaseModel):
    module_id: str
    module_name: str
    module_pin: str
    chip_pin: str
    function: str
    direction: str = "bidirectional"
    locked: bool = False

class RiskItem(BaseModel):
    level: str  # 错误 / 警告 / 提示
    code: str
    message: str
    suggestion: str
    item: Dict[str, Any] = {}
    pin: Optional[str] = None
    confidence: str = "high"
    weight: float = 0.0

# --- 请求模型 ---
class AllocateRequest(BaseModel):
    chip_id: Optional[str] = Field(None, description="芯片 ID，优先于 chip")
    chip: Optional[str] = Field(None, description="芯片 ID（兼容字段）")
    module_ids: Optional[List[str]] = Field(None, description="模块 ID 列表，优先于 modules")
    modules: Optional[List[str]] = Field(None, description="模块 ID 列表（兼容）")
    allocation: Optional[List[AllocationItem]] = Field(None, description="手动分配覆盖")
    locked_pins: Optional[Dict[str, str]] = Field(None, description="锁定引脚 {module_pin: chip_pin}")
    preferred_allocation: Optional[List[AllocationItem]] = Field(None, description="min_change 参考分配")
    strategy: str = Field("recommended", description="recommended / min_change")
    alternative_count: int = Field(3, ge=0, le=20, description="生成方案数")
    include_alternatives: bool = False
    explain_risks: bool = True
    project_path: Optional[str] = None
    use_detected_chip: bool = True
    project_name: str = "untitled_project"
    notes: str = ""
    chip_detection: Optional[Dict[str, Any]] = None

class ScanProjectRequest(AllocateRequest):
    project_path: str

class ProjectNameRequest(BaseModel):
    project_name: str = "untitled_project"

class SaveProjectRequest(BaseModel):
    project_name: str = "untitled_project"
    chip_id: Optional[str] = None
    module_ids: Optional[List[str]] = None
    allocation: Optional[List[AllocationItem]] = None
    risks: Optional[List[RiskItem]] = None
    notes: str = ""
    schema_version: int = 2

class ExportRequest(AllocateRequest):
    format: Optional[str] = None

class VersionCompareRequest(BaseModel):
    old_allocation: List[AllocationItem] = []
    new_allocation: List[AllocationItem] = []

class SimpleIdRequest(BaseModel):
    id: str

class PackageDirRequest(BaseModel):
    package_dir: str
    allow_downgrade: bool = False

class PathRequest(BaseModel):
    path: str

class RestoreRequest(BaseModel):
    backup_path: str

class DiagnosticsRequest(BaseModel):
    include_project_data: bool = False

class LockRequest(BaseModel):
    project_name: str = "default"
    actor: str = "anonymous"

class ReviewCreateRequest(BaseModel):
    project_name: str = "default"
    author: str = "anonymous"
    summary: str = ""
    changes: List[Any] = []

class ReviewUpdateRequest(BaseModel):
    review_id: str
    actor: str = "anonymous"
    status: Optional[str] = None
    comment: Optional[str] = None

class DesignReviewRequest(AllocateRequest):
    pass

class ReleaseBuildRequest(BaseModel):
    name: str = "EmbedPinDoctor"

class RuleImportRequest(BaseModel):
    package_dir: str

class CustomSaveRequest(BaseModel):
    data: Optional[Dict[str, Any]] = None
    id: Optional[str] = None

class EcosystemEnableRequest(BaseModel):
    id: str
    enabled: bool = True

class EventReadRequest(BaseModel):
    project_name: str = "default"

class KiCadImportRequest(BaseModel):
    path: str

# --- 响应模型 ---
class AllocateResponse(BaseModel):
    chip: ChipInfo
    modules: List[ModuleInfo]
    allocation: List[AllocationItem]
    risks: List[RiskItem]
    alternatives: List[List[AllocationItem]] = []
    scan: Optional[Dict[str, Any]] = None
    comparison: Optional[Dict[str, Any]] = None
    chip_detection: Optional[Dict[str, Any]] = None
