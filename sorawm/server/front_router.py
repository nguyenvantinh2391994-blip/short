from fastapi import APIRouter
from starlette.responses import FileResponse

from sorawm.configs import FRONTUI_DIST_DIR_ASSETS, FRONTUI_DIST_DIR_INDEX_HTML

router = APIRouter()


@router.get("/assets/{asset_path:path}")
def get_asset(asset_path: str):
    return FileResponse(FRONTUI_DIST_DIR_ASSETS / asset_path)


@router.get("/{full_path:path}")
def spa(full_path: str):
    if full_path.startswith("api/"):
        return {"detail": "Not Found"}
    return FileResponse(FRONTUI_DIST_DIR_INDEX_HTML)
