from django.urls import path
from .views import SecureSyncView, index, dashboard_stats, GatewayHandshakeView, threat_simulator
from .api_views import DashboardMetricsView, RecentLogsView, GatewayStatusView
from .user_sync_views import DeviceCommandQueueView, DeviceUserBackupView

urlpatterns = [
    path('', index, name='index'),
    path('api/v1/gateway/handshake/', GatewayHandshakeView.as_view(), name='gateway-handshake'),
    path('api/v1/gateway/sync/', SecureSyncView.as_view(), name='gateway-sync'),
    path('api/v1/gateway/commands/', DeviceCommandQueueView.as_view(), name='gateway-commands'),
    path('api/v1/gateway/users/backup/', DeviceUserBackupView.as_view(), name='gateway-users-backup'),
    path('api/v1/dashboard/metrics/', DashboardMetricsView.as_view(), name='dashboard-metrics'),
    path('api/v1/dashboard/recent-logs/', RecentLogsView.as_view(), name='dashboard-recent-logs'),
    path('api/v1/dashboard/gateways/', GatewayStatusView.as_view(), name='dashboard-gateways'),
    path('api/v1/dashboard/stats/', dashboard_stats, name='dashboard-stats'),
    path('simulator/', threat_simulator, name='threat-simulator'),
]
