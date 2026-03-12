from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    checks: dict


class SyncRequest(BaseModel):
    host: str | None = None


class SyncResponse(BaseModel):
    status: str
    message: str
    host: str
    files_synced: int


class NotebookSummary(BaseModel):
    id: str
    name: str
    page_count: int
    last_modified: str
    parent_id: str | None = None


class NotebookDetail(BaseModel):
    id: str
    name: str
    page_count: int
    last_modified: str
    pages: list[int]


class ItemSummary(BaseModel):
    id: str
    name: str
    type: str
    parent_id: str | None = None
    last_modified: str
    page_count: int


class FolderSummary(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    last_modified: str


class FolderTreeNode(BaseModel):
    id: str
    name: str
    type: str
    parent_id: str | None = None
    last_modified: str
    page_count: int
    children: list["FolderTreeNode"] = []


class SyncStatusResponse(BaseModel):
    last_sync: str | None = None
    last_sync_direction: str | None = None
    files_synced: int | None = None
    device_ip: str | None = None
    battery: int | None = None
    device_info_updated: str | None = None


class DeviceInfoRequest(BaseModel):
    ip: str
    battery: int | None = None
    push_files: int | None = None
    pull_files: int | None = None


class ToDeviceItem(BaseModel):
    id: str
    filename: str
    target_folder_id: str | None = None
    created_at: str
    size: int
