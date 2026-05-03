"""Tool registry: maps tool names → async handler functions.

Handlers live in user_tools.py and admin_tools.py. This module wires them
together with the config and audit logger.

Stubs only for now — implementations to be filled in tools modules.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from .audit import AuditLogger
from .config import AdminConfig, UserConfig

ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


def build_user_registry(config: UserConfig, audit: AuditLogger) -> dict[str, ToolHandler]:
    """Build the user-mode tool registry (IMAP/SMTP)."""
    from . import user_tools as ut

    ctx = ut.UserContext(config=config, audit=audit)

    return {
        # mailbox.read
        "list_inbox": ut.list_inbox(ctx),
        "read_message": ut.read_message(ctx),
        "get_message_raw": ut.get_message_raw(ctx),
        "search_messages": ut.search_messages(ctx),
        "get_unread_count": ut.get_unread_count(ctx),
        "download_attachment": ut.download_attachment(ctx),
        # mailbox.folders
        "list_folders": ut.list_folders(ctx),
        "create_folder": ut.create_folder(ctx),
        "rename_folder": ut.rename_folder(ctx),
        "delete_folder": ut.delete_folder(ctx),
        "empty_folder": ut.empty_folder(ctx),
        # mailbox.send
        "send_message": ut.send_message(ctx),
        "reply_to_message": ut.reply_to_message(ctx),
        "forward_message": ut.forward_message(ctx),
        "save_draft": ut.save_draft(ctx),
        # mailbox.flags
        "mark_read": ut.mark_read(ctx),
        "mark_unread": ut.mark_unread(ctx),
        "mark_flagged": ut.mark_flagged(ctx),
        "set_custom_flag": ut.set_custom_flag(ctx),
        "move_message": ut.move_message(ctx),
        "delete_message": ut.delete_message(ctx),
    }


def build_admin_registry(config: AdminConfig, audit: AuditLogger) -> dict[str, ToolHandler]:
    """Build the admin-mode tool registry (Mailcow REST API)."""
    from . import admin_tools as at

    ctx = at.AdminContext(config=config, audit=audit)

    return {
        # domain
        "domain_list": at.domain_list(ctx),
        "domain_create": at.domain_create(ctx),
        "domain_update": at.domain_update(ctx),
        "domain_delete": at.domain_delete(ctx),
        "domain_set_footer": at.domain_set_footer(ctx),
        "domain_set_tags": at.domain_set_tags(ctx),
        "domain_delete_tags": at.domain_delete_tags(ctx),
        # mailbox
        "mailbox_list": at.mailbox_list(ctx),
        "mailbox_list_by_domain": at.mailbox_list_by_domain(ctx),
        "mailbox_create": at.mailbox_create(ctx),
        "mailbox_update": at.mailbox_update(ctx),
        "mailbox_set_password": at.mailbox_set_password(ctx),
        "mailbox_delete": at.mailbox_delete(ctx),
        "mailbox_quota_report": at.mailbox_quota_report(ctx),
        "mailbox_set_tags": at.mailbox_set_tags(ctx),
        "mailbox_delete_tags": at.mailbox_delete_tags(ctx),
        "mailbox_set_acl": at.mailbox_set_acl(ctx),
        "mailbox_set_custom_attribute": at.mailbox_set_custom_attribute(ctx),
        # alias
        "alias_list": at.alias_list(ctx),
        "alias_create": at.alias_create(ctx),
        "alias_update": at.alias_update(ctx),
        "alias_delete": at.alias_delete(ctx),
        "time_limited_alias_list": at.time_limited_alias_list(ctx),
        "time_limited_alias_create": at.time_limited_alias_create(ctx),
        # app_password
        "app_password_list": at.app_password_list(ctx),
        "app_password_create": at.app_password_create(ctx),
        "app_password_delete": at.app_password_delete(ctx),
        # dkim
        "dkim_list": at.dkim_list(ctx),
        "dkim_create": at.dkim_create(ctx),
        "dkim_duplicate": at.dkim_duplicate(ctx),
        "dkim_delete": at.dkim_delete(ctx),
        # bcc
        "bcc_list": at.bcc_list(ctx),
        "bcc_create": at.bcc_create(ctx),
        "bcc_delete": at.bcc_delete(ctx),
        # recipient_map
        "recipient_map_list": at.recipient_map_list(ctx),
        "recipient_map_create": at.recipient_map_create(ctx),
        "recipient_map_delete": at.recipient_map_delete(ctx),
        # transport
        "transport_list": at.transport_list(ctx),
        "transport_create": at.transport_create(ctx),
        "transport_delete": at.transport_delete(ctx),
        # relayhost
        "relayhost_list": at.relayhost_list(ctx),
        "relayhost_create": at.relayhost_create(ctx),
        "relayhost_delete": at.relayhost_delete(ctx),
        # tls_policy
        "tls_policy_list": at.tls_policy_list(ctx),
        "tls_policy_create": at.tls_policy_create(ctx),
        "tls_policy_delete": at.tls_policy_delete(ctx),
        # forward_host
        "forward_host_list": at.forward_host_list(ctx),
        "forward_host_create": at.forward_host_create(ctx),
        "forward_host_delete": at.forward_host_delete(ctx),
        # sync_job
        "sync_job_list": at.sync_job_list(ctx),
        "sync_job_create": at.sync_job_create(ctx),
        "sync_job_update": at.sync_job_update(ctx),
        "sync_job_delete": at.sync_job_delete(ctx),
        # resource
        "resource_list": at.resource_list(ctx),
        "resource_create": at.resource_create(ctx),
        "resource_delete": at.resource_delete(ctx),
        # oauth2
        "oauth2_client_list": at.oauth2_client_list(ctx),
        "oauth2_client_create": at.oauth2_client_create(ctx),
        "oauth2_client_delete": at.oauth2_client_delete(ctx),
        # domain_admin
        "domain_admin_list": at.domain_admin_list(ctx),
        "domain_admin_create": at.domain_admin_create(ctx),
        "domain_admin_update": at.domain_admin_update(ctx),
        "domain_admin_set_acl": at.domain_admin_set_acl(ctx),
        "domain_admin_delete": at.domain_admin_delete(ctx),
        "domain_admin_sso_token": at.domain_admin_sso_token(ctx),
        # domain_policy
        "domain_policy_list_blacklist": at.domain_policy_list_blacklist(ctx),
        "domain_policy_list_whitelist": at.domain_policy_list_whitelist(ctx),
        "domain_policy_create": at.domain_policy_create(ctx),
        "domain_policy_delete": at.domain_policy_delete(ctx),
        # quarantine
        "quarantine_list": at.quarantine_list(ctx),
        "quarantine_release": at.quarantine_release(ctx),
        "quarantine_learn_spam": at.quarantine_learn_spam(ctx),
        "quarantine_delete": at.quarantine_delete(ctx),
        "quarantine_set_notification": at.quarantine_set_notification(ctx),
        # queue
        "queue_list": at.queue_list(ctx),
        "queue_flush": at.queue_flush(ctx),
        "queue_delete": at.queue_delete(ctx),
        # fail2ban
        "fail2ban_get": at.fail2ban_get(ctx),
        "fail2ban_update": at.fail2ban_update(ctx),
        "fail2ban_unban": at.fail2ban_unban(ctx),
        # ratelimit
        "ratelimit_get_mailbox": at.ratelimit_get_mailbox(ctx),
        "ratelimit_set_mailbox": at.ratelimit_set_mailbox(ctx),
        "ratelimit_get_domain": at.ratelimit_get_domain(ctx),
        "ratelimit_set_domain": at.ratelimit_set_domain(ctx),
        # spam
        "spam_score_get": at.spam_score_get(ctx),
        "spam_score_set": at.spam_score_set(ctx),
        # settings
        "cors_settings_update": at.cors_settings_update(ctx),
        "identity_provider_settings_update": at.identity_provider_settings_update(ctx),
        "pushover_set": at.pushover_set(ctx),
        # logs
        "logs_get_postfix": at.logs_get_postfix(ctx),
        "logs_get_dovecot": at.logs_get_dovecot(ctx),
        "logs_get_rspamd": at.logs_get_rspamd(ctx),
        "logs_get_sogo": at.logs_get_sogo(ctx),
        "logs_get_acme": at.logs_get_acme(ctx),
        "logs_get_netfilter": at.logs_get_netfilter(ctx),
        "logs_get_watchdog": at.logs_get_watchdog(ctx),
        "logs_get_api": at.logs_get_api(ctx),
        "logs_get_autodiscover": at.logs_get_autodiscover(ctx),
        "logs_get_ratelimit": at.logs_get_ratelimit(ctx),
        # status
        "server_version": at.server_version(ctx),
        "server_containers_status": at.server_containers_status(ctx),
        "server_vmail_status": at.server_vmail_status(ctx),
        "server_status_summary": at.server_status_summary(ctx),
        # delivery
        "send_test_mail": at.send_test_mail(ctx),
    }
