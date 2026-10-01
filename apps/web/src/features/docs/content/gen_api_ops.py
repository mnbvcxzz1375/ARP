#!/usr/bin/env python3
"""Generate the docs.api.op.* locale entries for en/zh docs.ts.

en values are taken VERBATIM from packages/protocol/openapi/agentnet.openapi.json
(the same artifact ApiReferencePage imports), so the English catalog never drifts
from the spec by hand. zh values are hand translations.

Rerun after regenerating the OpenAPI artifact:
    python apps/web/src/features/docs/content/gen_api_ops.py
The script FAILS if any operationId lacks a zh translation, so spec growth
cannot silently fall back to English.
"""

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[6]
SPEC = json.loads((REPO / 'packages/protocol/openapi/agentnet.openapi.json').read_text(encoding='utf-8'))

# operationId -> (summary_zh, description_zh or None)
ZH = {
    'healthz_healthz_get': (
        '存活探针（Healthz）',
        '轻量存活探针。\n\nAPI 进程运行时返回 200。不检查外部依赖，依赖检查请用 /readyz。',
    ),
    'readyz_readyz_get': (
        '就绪探针（Readyz）',
        '带依赖检查的深度就绪探针。\n\n检查 PostgreSQL 与 Redis 连通性。仅当全部依赖可达时返回 200，否则返回 503。\n\n同时更新 agentnet_health_check_status Prometheus gauge，依赖降级时触发告警。',
    ),
    'list_agents_endpoint_v1_agents_get': (
        '列出智能体',
        '分页列出已认证用户的智能体，支持按状态过滤与搜索。',
    ),
    'create_agent_endpoint_v1_agents_post': (
        '创建智能体',
        '注册一个归属于已认证用户的新智能体。响应中包含用于 WebSocket 连接的一次性智能体 token 明文。',
    ),
    'get_agent_endpoint_v1_agents__agent_id__get': (
        '获取智能体',
        '返回已认证用户拥有的一个智能体。',
    ),
    'delete_agent_endpoint_v1_agents__agent_id__delete': (
        '删除智能体',
        '删除已认证用户拥有的智能体。',
    ),
    'rotate_token_endpoint_v1_agents__agent_id__rotate_token_post': (
        '轮换智能体 token',
        '吊销智能体当前生效的 token 并签发新 token。新 token 明文仅在此响应中展示一次。',
    ),
    'list_approvals_v1_approvals_get': (
        '列出审批',
        '列出已认证用户的智能体所拥有的人工审批（human-in-the-loop）请求。',
    ),
    'accept_approval_v1_approvals__approval_id__accept_post': (
        '同意审批',
        '在验证目标智能体归属后同意一条待处理审批请求。',
    ),
    'reject_approval_v1_approvals__approval_id__reject_post': (
        '拒绝审批',
        '在验证目标智能体归属后拒绝一条待处理审批请求。',
    ),
    'list_api_keys_endpoint_v1_auth_api_keys_get': (
        '列出 API 密钥',
        '列出已认证用户拥有的 API 密钥。密钥明文不会返回。',
    ),
    'create_api_key_endpoint_v1_auth_api_keys_post': (
        '创建 API 密钥',
        '为已认证用户签发新 API 密钥。密钥明文仅返回一次。',
    ),
    'revoke_api_key_endpoint_v1_auth_api_keys__api_key_id__revoke_post': (
        '吊销 API 密钥',
        '吊销已认证用户拥有的 API 密钥。默认情况下拒绝吊销用户的最后一个有效密钥，避免意外锁定。',
    ),
    'register_v1_auth_register_post': (
        '注册或获取用户并签发 API 密钥',
        '用户不存在时创建用户，并返回新签发的 API 密钥。密钥明文仅在此响应中展示一次。',
    ),
    'list_connections_v1_connections_get': (
        '列出连接',
        '列出已认证用户首个智能体的连接记录。',
    ),
    'request_connection_v1_connections_request_post': (
        '请求智能体连接',
        '创建一条从用户首个智能体到目标 Agent Number 的待处理连接请求。',
    ),
    'accept_connection_v1_connections__connection_id__accept_post': (
        '同意连接请求',
        '在验证目标智能体归属后同意一条待处理连接请求。',
    ),
    'reject_connection_v1_connections__connection_id__reject_post': (
        '拒绝连接请求',
        '在验证目标智能体归属后拒绝一条待处理连接请求。',
    ),
    'list_circuit_breakers_v1_continuity_circuit_breakers_get': (
        '列出熔断器',
        '列出全部熔断器。',
    ),
    'reset_circuit_breaker_v1_continuity_circuit_breakers__breaker_id__reset_post': (
        '重置熔断器',
        '手动把熔断器重置为关闭状态。',
    ),
    'list_failover_configs_v1_continuity_failover_configs_get': (
        '列出故障转移配置',
        '列出全部故障转移配置。',
    ),
    'create_failover_config_v1_continuity_failover_configs_post': (
        '创建故障转移配置',
        '创建一条新的故障转移配置。',
    ),
    'list_failover_events_v1_continuity_failover_events_get': (
        '列出故障转移事件',
        '列出故障转移事件。',
    ),
    'trigger_manual_failover_v1_continuity_failover__config_id__trigger_post': (
        '触发手动故障转移',
        '手动触发一次故障转移。',
    ),
    'execute_manual_failover_v1_continuity_failover__event_id__execute_post': (
        '执行手动故障转移',
        '执行一条待处理的故障转移事件。',
    ),
    'rollback_manual_failover_v1_continuity_failover__event_id__rollback_post': (
        '回滚手动故障转移',
        '回滚一条已完成的故障转移事件。',
    ),
    'get_relay_health_v1_continuity_relay_health__relay_id__get': (
        '获取中继健康状态',
        '检查中继节点的健康状态。',
    ),
    'list_access_requests_admin_v1_dashboard_admin_access_requests_get': (
        '列出访问请求（管理员）',
        '列出访问请求。仅管理员可用。',
    ),
    'get_access_request_detail_v1_dashboard_admin_access_requests__request_id__get': (
        '获取访问请求详情',
        '获取单条访问请求的完整详情。仅管理员可用。',
    ),
    'approve_request_v1_dashboard_admin_access_requests__request_id__approve_post': (
        '批准请求',
        '批准一条访问请求。仅管理员可用。',
    ),
    'reject_request_v1_dashboard_admin_access_requests__request_id__reject_post': (
        '拒绝请求',
        '拒绝一条访问请求。仅管理员可用，且必须填写拒绝原因。',
    ),
    'list_agents_v1_dashboard_admin_agents_get': (
        '列出全部智能体',
        '列出所有用户的全部智能体。',
    ),
    'get_agent_detail_v1_dashboard_admin_agents__agent_id__get': (
        '获取智能体详情',
        '单个智能体的详情视图。',
    ),
    'disable_agent_v1_dashboard_admin_agents__agent_id__disable_post': (
        '禁用智能体',
        '禁用或重新启用智能体。要求 super_admin + step-up 认证。',
    ),
    'list_audit_logs_v1_dashboard_admin_audit_logs_get': (
        '列出审计日志',
        '列出审计日志条目。',
    ),
    'export_audit_logs_v1_dashboard_admin_audit_logs_export_get': (
        '导出审计日志',
        '分页导出 JSON 格式的审计日志。要求导出权限 + step-up 认证。',
    ),
    'list_dedicated_channels_v1_dashboard_admin_dedicated_channels_get': (
        '列出专属通道',
        '列出专属通道，支持可选过滤（管理员读取）。\n\n要求：admin:read\nconnection_config 与 encryption_config 中的密钥已遮蔽。\n审计：记录每次敏感通道配置元数据的读取。',
    ),
    'create_dedicated_channel_v1_dashboard_admin_dedicated_channels_post': (
        '创建专属通道',
        '创建一条新专属通道（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'get_dedicated_channel_v1_dashboard_admin_dedicated_channels__channel_id__get': (
        '获取专属通道',
        '按 ID 获取单个专属通道（管理员读取）。\n\n要求：admin:read',
    ),
    'update_dedicated_channel_v1_dashboard_admin_dedicated_channels__channel_id__patch': (
        '更新专属通道',
        '更新专属通道（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'delete_dedicated_channel_v1_dashboard_admin_dedicated_channels__channel_id__delete': (
        '删除专属通道',
        '删除（吊销）专属通道（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'disable_dedicated_channel_v1_dashboard_admin_dedicated_channels__channel_id__disable_post': (
        '禁用专属通道',
        '禁用专属通道（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'enable_dedicated_channel_v1_dashboard_admin_dedicated_channels__channel_id__enable_post': (
        '启用专属通道',
        '启用专属通道（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'trigger_health_check_v1_dashboard_admin_dedicated_channels__channel_id__health_check_post': (
        '触发健康检查',
        '对专属通道触发一次健康检查（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up\n健康检查是写操作（创建 ChannelHealthCheck 记录），不是读操作。\n审计：记录健康检查的调用与结果。',
    ),
    'list_health_checks_v1_dashboard_admin_dedicated_channels__channel_id__health_checks_get': (
        '列出健康检查',
        '列出专属通道的最近健康检查（管理员读取）。\n\n要求：admin:read\n审计：记录健康检查历史的读取。',
    ),
    'list_egress_logs_v1_dashboard_admin_egress_logs_get': (
        '列出出口日志',
        '列出出口日志，支持可选过滤（仅管理员）。\n\n返回出口网关请求日志，支持过滤与分页。\n\n要求：admin:read 权限',
    ),
    'get_admin_network_overview_v1_dashboard_admin_network_overview_get': (
        '获取管理员网络概览',
        '获取全部用户的网络概览统计（仅管理员）。\n\n返回系统中全部网络范围、网络区域与策略的统计。\n\n要求：admin:read 权限',
    ),
    'admin_overview_v1_dashboard_admin_overview_get': (
        '管理员概览',
        '平台级 KPI：用户、智能体、任务、worker 健康。',
    ),
    'system_health_v1_dashboard_admin_system_health_get': (
        '系统健康',
        '平台健康：数据库、Redis、worker、迁移版本。',
    ),
    'list_tasks_v1_dashboard_admin_tasks_get': (
        '列出全部任务',
        '列出所有智能体的全部任务。',
    ),
    'get_task_detail_v1_dashboard_admin_tasks__task_id__get': (
        '获取任务详情',
        '单个任务的详情视图，含 payload/结果预览。',
    ),
    'cancel_task_v1_dashboard_admin_tasks__task_id__cancel_post': (
        '取消任务',
        '取消待处理或运行中的任务。管理员可取消待处理任务；super_admin 可取消运行中任务。',
    ),
    'expire_task_v1_dashboard_admin_tasks__task_id__expire_post': (
        '强制过期任务',
        '强制让任务过期。仅 super_admin + step-up 可用。',
    ),
    'list_users_v1_dashboard_admin_users_get': (
        '列出用户',
        '列出全部用户及其分用户统计。',
    ),
    'get_user_detail_v1_dashboard_admin_users__user_id__get': (
        '获取用户详情',
        '单个用户的详情视图。',
    ),
    'disable_user_v1_dashboard_admin_users__user_id__disable_post': (
        '禁用用户',
        '禁用或重新启用用户。要求 super_admin + step-up 认证。',
    ),
    'force_revoke_keys_v1_dashboard_admin_users__user_id__force_revoke_keys_post': (
        '强制吊销密钥',
        '吊销某用户的全部 API 密钥。要求 super_admin + step-up 认证。',
    ),
    'list_agents_v1_dashboard_agents_get': ('列出智能体', None),
    'create_agent_v1_dashboard_agents_post': ('创建智能体', None),
    'get_agent_detail_v1_dashboard_agents__agent_id__get': ('获取智能体详情', None),
    'update_agent_v1_dashboard_agents__agent_id__patch': ('更新智能体', None),
    'delete_agent_v1_dashboard_agents__agent_id__delete': ('删除智能体', None),
    'update_firewall_v1_dashboard_agents__agent_id__firewall_patch': ('更新防火墙', None),
    'rotate_agent_token_v1_dashboard_agents__agent_id__rotate_token_post': ('轮换智能体 token', None),
    'list_api_keys_v1_dashboard_api_keys_get': ('列出 API 密钥', None),
    'create_api_key_v1_dashboard_api_keys_post': ('创建 API 密钥', None),
    'revoke_api_key_v1_dashboard_api_keys__api_key_id__revoke_post': ('吊销 API 密钥', None),
    'list_approvals_v1_dashboard_approvals_get': ('列出审批', None),
    'accept_approval_v1_dashboard_approvals__approval_id__accept_post': ('同意审批', None),
    'reject_approval_v1_dashboard_approvals__approval_id__reject_post': ('拒绝审批', None),
    'login_v1_dashboard_auth_login_post': (
        '登录',
        '用用户名 + API 密钥认证，创建会话并设置 cookie。',
    ),
    'logout_v1_dashboard_auth_logout_post': (
        '退出登录',
        '吊销当前会话并清除 cookie。',
    ),
    'me_v1_dashboard_auth_me_get': (
        '当前用户',
        '返回当前用户与会话信息。',
    ),
    'step_up_v1_dashboard_auth_step_up_post': (
        'Step-up 认证',
        '重新验证 API 密钥以延长 step-up 有效窗口。',
    ),
    'get_connections_v1_dashboard_connections_get': ('获取连接', None),
    'accept_connection_v1_dashboard_connections__connection_id__accept_post': ('同意连接', None),
    'reject_connection_v1_dashboard_connections__connection_id__reject_post': ('拒绝连接', None),
    'get_user_network_overview_v1_dashboard_network_overview_get': (
        '获取用户网络概览',
        '获取当前用户的网络概览统计。\n\n返回该用户拥有的网络范围、网络区域与策略的统计。',
    ),
    'overview_v1_dashboard_overview_get': ('概览', None),
    'list_tasks_v1_dashboard_tasks_get': ('列出任务', None),
    'get_task_detail_v1_dashboard_tasks__task_id__get': ('获取任务详情', None),
    'get_task_messages_v1_dashboard_tasks__task_id__messages_get': ('获取任务消息', None),
    'get_task_progress_v1_dashboard_tasks__task_id__progress_get': ('获取任务进度', None),
    'edge_relay_heartbeat_v1_personal_edge_relay_heartbeat_post': (
        '边缘中继心跳',
        '处理个人边缘中继发来的心跳。',
    ),
    'register_edge_relay_v1_personal_edge_relay_register_post': (
        '注册边缘中继',
        '注册一个个人边缘中继。',
    ),
    'list_edge_relays_v1_personal_edge_relays_get': (
        '列出边缘中继',
        '列出当前用户的全部个人边缘中继。',
    ),
    'get_personal_scope_v1_personal_scope_get': (
        '获取个人范围',
        '获取当前用户的个人范围配置。\n\n不存在时自动创建。',
    ),
    'update_personal_scope_v1_personal_scope_patch': (
        '更新个人范围',
        '更新个人范围配置。',
    ),
    'submit_access_request_v1_public_access_requests_post': (
        '提交访问请求',
        '提交公开访问请求。无需认证。要求持久化存储。',
    ),
    'list_relay_nodes_v1_relay_nodes_get': (
        '列出中继节点',
        '列出中继节点，支持可选过滤。',
    ),
    'register_relay_node_v1_relay_nodes_register_post': (
        '注册中继节点',
        '注册一个新中继节点。\n\n普通用户只能注册 personal_edge 节点。\n管理员可注册任意节点类型。',
    ),
    'relay_node_heartbeat_v1_relay_nodes__relay_node_id__heartbeat_post': (
        '中继节点心跳',
        '通过心跳更新中继节点健康指标。',
    ),
    'list_route_decisions_v1_routes_decisions_get': (
        '列出路由决策',
        '列出路由决策，支持按任务过滤。\n\n仅返回用户拥有发送方或接收方智能体的任务决策。',
    ),
    'get_route_decision_v1_routes_decisions__route_decision_id__get': (
        '获取路由决策',
        '按 ID 获取一条路由决策。\n\n仅当用户拥有发送方或接收方智能体时才返回该决策。',
    ),
    'list_policies_v1_routes_policies_get': (
        '列出策略',
        '列出路由策略，支持可选过滤。\n\n要求：policy:read 权限',
    ),
    'create_policy_v1_routes_policies_post': (
        '创建策略',
        '创建一条新路由策略。\n\n要求：policy:manage 权限',
    ),
    'update_policy_v1_routes_policies__policy_id__patch': (
        '更新策略',
        '更新已有路由策略。\n\n要求：policy:manage 权限',
    ),
    'query_sla_metrics_v1_sla_metrics_get': (
        '查询 SLA 指标',
        '查询某个网络范围（scope）的当前指标值。',
    ),
    'generate_sla_report_v1_sla_report_get': (
        '生成 SLA 报告',
        '生成 SLA 合规报告。',
    ),
    'list_sla_targets_v1_sla_targets_get': (
        '列出 SLA 目标',
        '列出全部 SLA 目标。',
    ),
    'create_sla_target_v1_sla_targets_post': (
        '创建 SLA 目标',
        '创建一个新 SLA 目标。',
    ),
    'list_sla_violations_v1_sla_violations_get': (
        '列出 SLA 违规',
        '列出 SLA 违规记录。',
    ),
    'list_tasks_endpoint_v1_tasks_get': (
        '列出任务',
        '列出已认证用户可见的任务，支持按状态过滤。',
    ),
    'create_task_endpoint_v1_tasks_post': (
        '创建任务',
        '创建一条从已拥有的发送方智能体到目标 Agent Number 的异步任务。投递立即在线路由，或存为离线投递。',
    ),
    'get_task_endpoint_v1_tasks__task_id__get': (
        '获取任务',
        '返回已认证用户拥有、或其智能体被指派的任务。',
    ),
    'list_task_delivery_events_v1_tasks__task_id__delivery_events_get': (
        '列出任务投递事件',
        '列出指定任务的投递事件（投递时间线）。\n\n仅当用户拥有发送方或接收方智能体时才返回。',
    ),
    'get_task_messages_endpoint_v1_tasks__task_id__messages_get': (
        '列出任务消息',
        '验证用户归属后返回任务的持久化消息。',
    ),
    'get_task_progress_endpoint_v1_tasks__task_id__progress_get': (
        '列出任务进度',
        '验证用户归属后返回任务的历史进度条目。',
    ),
    'list_task_route_decisions_v1_tasks__task_id__route_decisions_get': (
        '列出任务路由决策',
        '列出指定任务的路由决策。\n\n仅当用户拥有发送方或接收方智能体时才返回。',
    ),
    # --- 访问申请审计 ---
    'get_access_request_audit_trail_v1_dashboard_admin_access_requests__request_id__audit_trail_get': (
        '获取访问申请审计轨迹',
        '返回某条访问申请的完整审计轨迹（管理员读取）。\n\n要求：admin:read',
    ),
    # --- 用户偏好与资料 ---
    'get_preferences_v1_dashboard_auth_me_preferences_get': (
        '获取用户偏好',
        '返回当前登录用户的界面偏好（语言、主题、字号等）。',
    ),
    'update_preferences_v1_dashboard_auth_me_preferences_patch': (
        '更新用户偏好',
        '部分更新当前登录用户的界面偏好（会话鉴权 + CSRF）。\n\n审计：记录偏好的写入。',
    ),
    'update_profile_v1_dashboard_auth_me_profile_patch': (
        '更新用户资料',
        '更新当前登录用户的资料（如用户名）。\n\n用户名是可重复的显示标签，系统内部以 user_id（UUID）作为唯一标识。\n审计：记录资料更新。',
    ),
    # --- 出口网关 ---
    'list_egress_gateways_v1_egress_gateways_get': (
        '列出口网关',
        '列出口网关目录（管理员读取）。\n\n返回全部记录（按创建时间倒序），控制台在客户端做过滤。\n\n要求：admin:read\n审计：记录网关配置元数据的读取。',
    ),
    'create_egress_gateway_v1_egress_gateways_post': (
        '创建出口网关',
        '创建一个出口网关（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up\nsecret_store_ref 是密钥库引用（如 env:VAR_NAME），不是密钥值本身。',
    ),
    'get_egress_gateway_v1_egress_gateways__gateway_id__get': (
        '获取出口网关',
        '按 ID 获取单个出口网关（管理员读取）。\n\n要求：admin:read',
    ),
    'update_egress_gateway_v1_egress_gateways__gateway_id__patch': (
        '更新出口网关',
        '部分更新出口网关（要求 super_admin + step-up 认证）。\n\n要求：super_admin:write + step-up',
    ),
    'delete_egress_gateway_v1_egress_gateways__gateway_id__delete': (
        '删除出口网关',
        '删除出口网关（要求 super_admin + step-up 认证）。\n\n引用该网关的智能体不受影响：agents.egress_gateway_id 为 ON DELETE SET NULL，出口回退为直连。\n要求：super_admin:write + step-up',
    ),
    # --- 组织 ---
    'list_my_organizations_v1_organizations_mine_get': (
        '列出我的组织',
        '返回当前登录用户所属的组织列表。',
    ),
    'create_organization_v1_organizations_post': (
        '创建组织',
        '创建一个新组织（要求 super_admin + step-up 认证）。',
    ),
    'get_organization_v1_organizations__org_id__get': (
        '获取组织',
        '按 ID 获取单个组织详情。',
    ),
    'delete_organization_v1_organizations__org_id__delete': (
        '删除组织',
        '删除组织（要求 super_admin + step-up 认证）。',
    ),
    'list_organization_members_v1_organizations__org_id__members_get': (
        '列出组织成员',
        '列出指定组织的成员及其成员角色。',
    ),
    'add_organization_member_v1_organizations__org_id__members_post': (
        '添加组织成员',
        '向组织添加一名成员（要求 super_admin + step-up 认证）。',
    ),
    'update_organization_member_role_v1_organizations__org_id__members__user_id__patch': (
        '更新组织成员角色',
        '更新某成员在组织中的角色（manager/member）（要求 super_admin + step-up 认证）。',
    ),
    'remove_organization_member_v1_organizations__org_id__members__user_id__delete': (
        '移除组织成员',
        '将成员从组织中移除（要求 super_admin + step-up 认证）。',
    ),
    # --- 网络范围 / 区域（新 ID） ---
    'list_network_scopes_v1_dashboard_admin_network_scopes_get': (
        '列出网络范围',
        '列出平台上的全部网络范围（管理员读取）。\n\n要求：admin:read',
    ),
    'create_network_scope_v1_dashboard_admin_network_scopes_post': (
        '创建网络范围',
        '创建一个网络范围（要求 super_admin + step-up 认证）。',
    ),
    'get_network_scope_v1_dashboard_admin_network_scopes__scope_id__get': (
        '获取网络范围',
        '按 ID 获取单个网络范围（管理员读取）。\n\n要求：admin:read',
    ),
    'update_network_scope_v1_dashboard_admin_network_scopes__scope_id__put': (
        '更新网络范围',
        '更新网络范围（要求 super_admin + step-up 认证）。',
    ),
    'delete_network_scope_v1_dashboard_admin_network_scopes__scope_id__delete': (
        '删除网络范围',
        '删除网络范围及其子区域（要求 super_admin + step-up 认证）。',
    ),
    'list_network_zones_v1_dashboard_admin_network_zones_get': (
        '列出网络区域',
        '列出平台上的全部网络区域（管理员读取）。\n\n要求：admin:read',
    ),
    'create_network_zone_v1_dashboard_admin_network_zones_post': (
        '创建网络区域',
        '创建一个网络区域（要求 super_admin + step-up 认证）。',
    ),
    'get_network_zone_v1_dashboard_admin_network_zones__zone_id__get': (
        '获取网络区域',
        '按 ID 获取单个网络区域（管理员读取）。\n\n要求：admin:read',
    ),
    'update_network_zone_v1_dashboard_admin_network_zones__zone_id__put': (
        '更新网络区域',
        '更新网络区域（要求 super_admin + step-up 认证）。',
    ),
    'delete_network_zone_v1_dashboard_admin_network_zones__zone_id__delete': (
        '删除网络区域',
        '删除网络区域（要求 super_admin + step-up 认证）。',
    ),
}


def collect_ops(spec):
    ops = []
    for path, item in spec.get('paths', {}).items():
        for method in ['get', 'post', 'put', 'patch', 'delete', 'head', 'options']:
            if method in item:
                op = item[method]
                oid = op.get('operationId')
                if oid:
                    ops.append((oid, op.get('summary', '') or '', op.get('description', '') or ''))
    return ops


def ts_quote(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n') + "'"


def main():
    ops = collect_ops(SPEC)
    spec_ids = {oid for oid, _, _ in ops}
    missing = sorted(spec_ids - set(ZH))
    extra = sorted(set(ZH) - spec_ids)
    if missing:
        raise SystemExit(f'MISSING zh translations for: {missing}')
    if extra:
        raise SystemExit(f'zh translations for unknown operationIds (removed from spec?): {extra}')

    fragments = {}
    for locale in ('en', 'zh'):
        lines = []
        for oid, summary, description in ops:
            if locale == 'en':
                zh_summary, zh_desc = summary, description
            else:
                zh_summary, zh_desc = ZH[oid]
            lines.append(f"  'api.op.{oid}.summary': {ts_quote(zh_summary)},")
            desc = description if locale == 'en' else zh_desc
            if desc:
                lines.append(f"  'api.op.{oid}.description': {ts_quote(desc)},")
        fragments[locale] = '\n'.join(lines)

    out = Path(__file__).parent
    (out / 'api_ops.en.ts.txt').write_text(fragments['en'] + '\n', encoding='utf-8')
    (out / 'api_ops.zh.ts.txt').write_text(fragments['zh'] + '\n', encoding='utf-8')
    print(f'ops: {len(ops)}  keys: en summaries {len(ops)}, '
          f'en descriptions {sum(1 for _, _, d in ops if d)}')


if __name__ == '__main__':
    main()
