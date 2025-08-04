"""Admin API routes for monitoring and statistics."""
from fastapi import APIRouter, Depends, Request
from typing import Dict, Any, List
from datetime import datetime, timedelta, timezone
import psutil
import os

from ..core.auth import require_admin
from ..services.converter import WorkerPool


router = APIRouter(prefix="/api/admin", tags=["admin"])


# In-memory stats storage (in production, use Redis or a database)
conversion_stats = {
    "total_requests": 0,
    "successful_conversions": 0,
    "failed_conversions": 0,
    "conversions_by_type": {},
    "recent_conversions": [],
    "hourly_requests": {},
}


def update_conversion_stats(
    filename: str,
    file_type: str,
    file_size: int,
    duration: float,
    status: str
):
    """Update conversion statistics."""
    conversion_stats["total_requests"] += 1
    
    if status == "success":
        conversion_stats["successful_conversions"] += 1
    else:
        conversion_stats["failed_conversions"] += 1
    
    # Track by file type
    if file_type not in conversion_stats["conversions_by_type"]:
        conversion_stats["conversions_by_type"][file_type] = 0
    conversion_stats["conversions_by_type"][file_type] += 1
    
    # Track hourly
    current_hour = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:00")
    if current_hour not in conversion_stats["hourly_requests"]:
        conversion_stats["hourly_requests"][current_hour] = 0
    conversion_stats["hourly_requests"][current_hour] += 1
    
    # Add to recent conversions
    conversion_stats["recent_conversions"].insert(0, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "file_type": file_type,
        "file_size": file_size,
        "duration": round(duration, 2),
        "status": status
    })
    
    # Keep only last 100 conversions
    conversion_stats["recent_conversions"] = conversion_stats["recent_conversions"][:100]


@router.get("/stats")
async def get_admin_stats(
    request: Request,
    admin_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, Any]:
    """Get comprehensive admin statistics."""
    # Get worker pool
    worker_pool: WorkerPool = request.app.state.worker_pool
    
    # Calculate success rate
    total = conversion_stats["total_requests"]
    success_rate = 0
    if total > 0:
        success_rate = round(
            (conversion_stats["successful_conversions"] / total) * 100, 1
        )
    
    # Calculate average response time from recent conversions
    recent_times = [
        c["duration"] for c in conversion_stats["recent_conversions"]
        if c["status"] == "success" and c["duration"] > 0
    ]
    avg_response_time = 0
    if recent_times:
        avg_response_time = round(sum(recent_times) / len(recent_times), 2)
    
    # Get worker information
    workers = []
    if hasattr(worker_pool, 'conversion_service') and hasattr(worker_pool.conversion_service, 'executor'):
        executor = worker_pool.conversion_service.executor
        if executor:
            # Get number of workers
            num_workers = worker_pool.worker_count
            
            # Simulate worker status (in production, track actual worker states)
            for i in range(num_workers):
                workers.append({
                    "id": i + 1,
                    "status": "idle",  # In production, track actual status
                    "pid": os.getpid(),  # In production, get actual worker PID
                    "tasks_completed": conversion_stats["successful_conversions"] // num_workers
                })
    
    # Prepare hourly request data for chart
    now = datetime.now(timezone.utc)
    request_history = {
        "labels": [],
        "data": []
    }
    
    for i in range(24):
        hour = now - timedelta(hours=23-i)
        hour_key = hour.strftime("%Y-%m-%d %H:00")
        hour_label = hour.strftime("%H:00")
        
        request_history["labels"].append(hour_label)
        request_history["data"].append(
            conversion_stats["hourly_requests"].get(hour_key, 0)
        )
    
    # Get system stats
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    
    return {
        "total_requests": conversion_stats["total_requests"],
        "successful_conversions": conversion_stats["successful_conversions"],
        "failed_conversions": conversion_stats["failed_conversions"],
        "success_rate": success_rate,
        "avg_response_time": avg_response_time,
        "active_workers": len(workers),
        "workers": workers,
        "file_types": conversion_stats["conversions_by_type"],
        "recent_conversions": conversion_stats["recent_conversions"][:20],
        "request_history": request_history,
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_used_mb": memory.used // (1024 * 1024),
            "memory_total_mb": memory.total // (1024 * 1024)
        }
    }


@router.post("/clear-stats")
async def clear_stats(
    admin_user: Dict[str, Any] = Depends(require_admin)
) -> Dict[str, str]:
    """Clear all statistics."""
    global conversion_stats
    conversion_stats = {
        "total_requests": 0,
        "successful_conversions": 0,
        "failed_conversions": 0,
        "conversions_by_type": {},
        "recent_conversions": [],
        "hourly_requests": {},
    }
    return {"message": "Statistics cleared successfully"}