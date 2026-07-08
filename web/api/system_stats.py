from pathlib import Path

from flask import Blueprint, jsonify

system_stats_bp = Blueprint('system_stats', __name__)


@system_stats_bp.route('/api/system-stats')
def get_system_stats():
    try:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.3)
        cpu_count = psutil.cpu_count()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage(Path(__file__).resolve().parents[1] / 'outputs')

        return jsonify({
            'success': True,
            'cpu': {
                'percent': cpu_percent,
                'count': cpu_count,
            },
            'memory': {
                'percent': mem.percent,
                'total_gb': round(mem.total / (1024 ** 3), 1),
                'used_gb': round(mem.used / (1024 ** 3), 1),
                'available_gb': round(mem.available / (1024 ** 3), 1),
            },
            'disk': {
                'percent': disk.percent,
                'free_gb': round(disk.free / (1024 ** 3), 1),
                'total_gb': round(disk.total / (1024 ** 3), 1),
            },
        })
    except ImportError:
        return jsonify({
            'success': False,
            'error': 'psutil not installed',
        }), 503
