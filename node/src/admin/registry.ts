/**
 * Admin-mode registry: maps tool names to their handler factories.
 * Mirrors py/src/mcp_mailcow/registry.py (build_admin_registry).
 */
import type { AdminConfig } from "../config.js";
import type { AuditLogger } from "../audit.js";
import * as h from "./handlers.js";

type Handler = (args: unknown) => Promise<unknown>;

export function buildAdminRegistry(
  config: AdminConfig,
  audit: AuditLogger,
): Record<string, Handler> {
  const ctx = h.makeContext(config, audit);
  const wrap = (factory: (c: h.AdminContext) => h.Handler): Handler => {
    const fn = factory(ctx);
    return (args: unknown) => fn((args as Record<string, unknown>) ?? {});
  };

  return {
    // domain
    domain_list: wrap(h.domain_list),
    domain_create: wrap(h.domain_create),
    domain_update: wrap(h.domain_update),
    domain_delete: wrap(h.domain_delete),
    domain_set_footer: wrap(h.domain_set_footer),
    domain_set_tags: wrap(h.domain_set_tags),
    domain_delete_tags: wrap(h.domain_delete_tags),
    // mailbox
    mailbox_list: wrap(h.mailbox_list),
    mailbox_list_by_domain: wrap(h.mailbox_list_by_domain),
    mailbox_create: wrap(h.mailbox_create),
    mailbox_update: wrap(h.mailbox_update),
    mailbox_set_password: wrap(h.mailbox_set_password),
    mailbox_delete: wrap(h.mailbox_delete),
    mailbox_quota_report: wrap(h.mailbox_quota_report),
    mailbox_set_tags: wrap(h.mailbox_set_tags),
    mailbox_delete_tags: wrap(h.mailbox_delete_tags),
    mailbox_set_acl: wrap(h.mailbox_set_acl),
    mailbox_set_custom_attribute: wrap(h.mailbox_set_custom_attribute),
    // alias
    alias_list: wrap(h.alias_list),
    alias_create: wrap(h.alias_create),
    alias_update: wrap(h.alias_update),
    alias_delete: wrap(h.alias_delete),
    time_limited_alias_list: wrap(h.time_limited_alias_list),
    time_limited_alias_create: wrap(h.time_limited_alias_create),
    // app password
    app_password_list: wrap(h.app_password_list),
    app_password_create: wrap(h.app_password_create),
    app_password_delete: wrap(h.app_password_delete),
    // dkim
    dkim_list: wrap(h.dkim_list),
    dkim_create: wrap(h.dkim_create),
    dkim_duplicate: wrap(h.dkim_duplicate),
    dkim_delete: wrap(h.dkim_delete),
    // bcc, recipient_map, transport, relayhost, tls, forward_host
    bcc_list: wrap(h.bcc_list),
    bcc_create: wrap(h.bcc_create),
    bcc_delete: wrap(h.bcc_delete),
    recipient_map_list: wrap(h.recipient_map_list),
    recipient_map_create: wrap(h.recipient_map_create),
    recipient_map_delete: wrap(h.recipient_map_delete),
    transport_list: wrap(h.transport_list),
    transport_create: wrap(h.transport_create),
    transport_delete: wrap(h.transport_delete),
    relayhost_list: wrap(h.relayhost_list),
    relayhost_create: wrap(h.relayhost_create),
    relayhost_delete: wrap(h.relayhost_delete),
    tls_policy_list: wrap(h.tls_policy_list),
    tls_policy_create: wrap(h.tls_policy_create),
    tls_policy_delete: wrap(h.tls_policy_delete),
    forward_host_list: wrap(h.forward_host_list),
    forward_host_create: wrap(h.forward_host_create),
    forward_host_delete: wrap(h.forward_host_delete),
    // sync_job, resource, oauth2
    sync_job_list: wrap(h.sync_job_list),
    sync_job_create: wrap(h.sync_job_create),
    sync_job_update: wrap(h.sync_job_update),
    sync_job_delete: wrap(h.sync_job_delete),
    resource_list: wrap(h.resource_list),
    resource_create: wrap(h.resource_create),
    resource_delete: wrap(h.resource_delete),
    oauth2_client_list: wrap(h.oauth2_client_list),
    oauth2_client_create: wrap(h.oauth2_client_create),
    oauth2_client_delete: wrap(h.oauth2_client_delete),
    // domain_admin, domain_policy
    domain_admin_list: wrap(h.domain_admin_list),
    domain_admin_create: wrap(h.domain_admin_create),
    domain_admin_update: wrap(h.domain_admin_update),
    domain_admin_set_acl: wrap(h.domain_admin_set_acl),
    domain_admin_delete: wrap(h.domain_admin_delete),
    domain_admin_sso_token: wrap(h.domain_admin_sso_token),
    domain_policy_list_blacklist: wrap(h.domain_policy_list_blacklist),
    domain_policy_list_whitelist: wrap(h.domain_policy_list_whitelist),
    domain_policy_create: wrap(h.domain_policy_create),
    domain_policy_delete: wrap(h.domain_policy_delete),
    // quarantine, queue, fail2ban, ratelimit, spam, settings
    quarantine_list: wrap(h.quarantine_list),
    quarantine_release: wrap(h.quarantine_release),
    quarantine_learn_spam: wrap(h.quarantine_learn_spam),
    quarantine_delete: wrap(h.quarantine_delete),
    quarantine_set_notification: wrap(h.quarantine_set_notification),
    queue_list: wrap(h.queue_list),
    queue_flush: wrap(h.queue_flush),
    queue_delete: wrap(h.queue_delete),
    fail2ban_get: wrap(h.fail2ban_get),
    fail2ban_update: wrap(h.fail2ban_update),
    fail2ban_unban: wrap(h.fail2ban_unban),
    ratelimit_get_mailbox: wrap(h.ratelimit_get_mailbox),
    ratelimit_set_mailbox: wrap(h.ratelimit_set_mailbox),
    ratelimit_get_domain: wrap(h.ratelimit_get_domain),
    ratelimit_set_domain: wrap(h.ratelimit_set_domain),
    spam_score_get: wrap(h.spam_score_get),
    spam_score_set: wrap(h.spam_score_set),
    cors_settings_update: wrap(h.cors_settings_update),
    identity_provider_settings_update: wrap(h.identity_provider_settings_update),
    pushover_set: wrap(h.pushover_set),
    // logs
    logs_get_postfix: wrap(h.logs_get_postfix),
    logs_get_dovecot: wrap(h.logs_get_dovecot),
    logs_get_rspamd: wrap(h.logs_get_rspamd),
    logs_get_sogo: wrap(h.logs_get_sogo),
    logs_get_acme: wrap(h.logs_get_acme),
    logs_get_netfilter: wrap(h.logs_get_netfilter),
    logs_get_watchdog: wrap(h.logs_get_watchdog),
    logs_get_api: wrap(h.logs_get_api),
    logs_get_autodiscover: wrap(h.logs_get_autodiscover),
    logs_get_ratelimit: wrap(h.logs_get_ratelimit),
    // status
    server_version: wrap(h.server_version),
    server_containers_status: wrap(h.server_containers_status),
    server_vmail_status: wrap(h.server_vmail_status),
    server_status_summary: wrap(h.server_status_summary),
    // delivery
    send_test_mail: wrap(h.send_test_mail),
  };
}
