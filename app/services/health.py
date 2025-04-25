# app/services/health.py

from typing import Dict, Any
import psutil
from datetime import datetime

from app.utils.logger import get_logger

logger = get_logger(__name__)

class HealthChecker:
    """Service for checking application health status."""

    # Thresholds for system health
    CPU_THRESHOLD = 90.0
    MEMORY_THRESHOLD = 90.0

    async def check(self) -> Dict[str, Any]:
        """
        Check the health of various application components.

        Returns:
            Dict[str, Any]: Detailed health status of each component
        """
        try:
            system_health = self._check_system_health()

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "api": {
                    "status": "healthy",
                    "uptime": self._get_uptime()
                },
                "system": system_health,
                # Placeholder for future components
                # "database": await self._check_database(),
                # "cache": await self._check_cache(),
                # "ai_service": await self._check_ai_service(),
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "unhealthy",
                "error": str(e)
            }

    def _check_system_health(self) -> Dict[str, Any]:
        """
        Check system resources (CPU, memory).

        Returns:
            Dict[str, Any]: Detailed system health metrics
        """
        try:
            # Get CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            cpu_healthy = cpu_usage <= self.CPU_THRESHOLD

            # Get memory usage
            memory = psutil.virtual_memory()
            memory_healthy = memory.percent <= self.MEMORY_THRESHOLD

            # Log warnings if thresholds are exceeded
            if not cpu_healthy:
                logger.warning(f"High CPU usage: {cpu_usage}%")
            if not memory_healthy:
                logger.warning(f"High memory usage: {memory.percent}%")

            return {
                "status": "healthy" if (cpu_healthy and memory_healthy) else "unhealthy",
                "metrics": {
                    "cpu": {
                        "usage_percent": cpu_usage,
                        "status": "healthy" if cpu_healthy else "critical",
                        "threshold": self.CPU_THRESHOLD
                    },
                    "memory": {
                        "total": memory.total,
                        "available": memory.available,
                        "used_percent": memory.percent,
                        "status": "healthy" if memory_healthy else "critical",
                        "threshold": self.MEMORY_THRESHOLD
                    }
                }
            }
        except Exception as e:
            logger.error(f"System health check failed: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _get_uptime(self) -> float:
        """Get system uptime in seconds."""
        try:
            return psutil.boot_time()
        except Exception as e:
            logger.error(f"Failed to get uptime: {str(e)}")
            return 0.0

    # Example additional health checks (commented out for now):
    """
    async def _check_database(self) -> Dict[str, Any]:
        try:
            # Add your database connection check here
            return {
                "status": "healthy",
                "latency_ms": 0.0  # Add actual latency check
            }
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def _check_cache(self) -> Dict[str, Any]:
        try:
            # Add your cache connection check here
            return {
                "status": "healthy",
                "latency_ms": 0.0
            }
        except Exception as e:
            logger.error(f"Cache health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

    async def _check_ai_service(self) -> Dict[str, Any]:
        try:
            # Add your AI service check here
            return {
                "status": "healthy",
                "latency_ms": 0.0
            }
        except Exception as e:
            logger.error(f"AI service health check failed: {str(e)}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    """