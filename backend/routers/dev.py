"""
Dev-only endpoints: frontend rebuild and server restart.
These are intended for local development use only.
"""
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/dev", tags=["dev"])
logger = logging.getLogger(__name__)

# Project root is three levels up from this file (routers/ → backend/ → project root)
PROJECT_ROOT  = Path(__file__).parent.parent.parent
FRONTEND_DIR  = PROJECT_ROOT / "frontend"


@router.post("/rebuild")
def rebuild():
    """
    Run `npm run build` in the frontend directory.
    Returns { success, stdout, stderr }.
    """
    logger.info("Dev rebuild triggered — running npm run build in %s", FRONTEND_DIR)
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        success = result.returncode == 0
        if success:
            logger.info("Frontend build succeeded")
        else:
            logger.warning("Frontend build failed (exit %d)", result.returncode)
        return {
            "success":  success,
            "stdout":   result.stdout,
            "stderr":   result.stderr,
            "exit_code": result.returncode,
        }
    except FileNotFoundError:
        msg = "npm not found — is Node.js installed and on PATH?"
        logger.error(msg)
        return {"success": False, "stdout": "", "stderr": msg, "exit_code": -1}
    except subprocess.TimeoutExpired:
        msg = "npm run build timed out after 120 seconds"
        logger.error(msg)
        return {"success": False, "stdout": "", "stderr": msg, "exit_code": -1}
    except Exception as e:
        logger.error("Rebuild error: %s", e)
        return {"success": False, "stdout": "", "stderr": str(e), "exit_code": -1}


@router.post("/restart")
def restart():
    """
    Restart the server process.

    Strategy depends on how uvicorn was launched:
    - With --reload (dev mode): uvicorn runs a supervisor + worker pair.
      The supervisor holds the port; the worker handles requests.
      Sending SIGTERM to the worker (this process) causes the supervisor to
      immediately spawn a fresh worker — no port conflict.
    - Without --reload (prod/simple mode): os.execv replaces the single
      process directly, cleanly re-binding the port.
    """
    import signal

    def _do_restart():
        import time
        time.sleep(0.8)
        if "--reload" in sys.argv:
            # Reloader supervisor will restart a new worker automatically
            logger.info("Dev restart — sending SIGTERM to worker (reloader will respawn)")
            os.kill(os.getpid(), signal.SIGTERM)
        else:
            logger.info("Dev restart — re-exec %s %s", sys.executable, sys.argv)
            os.execv(sys.executable, [sys.executable] + sys.argv)

    threading.Thread(target=_do_restart, daemon=True).start()
    return {"restarting": True}
