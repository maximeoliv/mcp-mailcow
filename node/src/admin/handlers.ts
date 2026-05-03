/**
 * Admin tool handlers — TypeScript implementations.
 *
 * Mirrors py/src/mcp_mailcow/admin_tools.py. Patterns:
 *  - each tool is a factory `<name>(ctx) -> Handler` returning an async fn
 *  - destructive ops require `confirm: true` in args
 *  - audit logging is wrapped in `ctx.audit.trace(...)`
 *
 * For brevity, this file groups handlers by category. Type-safety is loose on
 * the args (record of unknown) — full Zod validation TBD in a later PR.
 */
import type { AdminConfig } from "../config.js";
import type { AuditLogger } from "../audit.js";
import { ConfirmationRequired } from "../exceptions.js";
import { MailcowClient } from "./api.js";

type Args = Record<string, unknown>;
export type Handler = (args: Args) => Promise<unknown>;

export interface AdminContext {
  config: AdminConfig;
  audit: AuditLogger;
  client(): MailcowClient;
}

export function makeContext(config: AdminConfig, audit: AuditLogger): AdminContext {
  return {
    config,
    audit,
    client: () =>
      new MailcowClient({
        baseUrl: config.baseUrl,
        apiKey: config.apiKey,
        tlsVerify: config.tlsVerify,
      }),
  };
}

const b = (v: unknown): number => (v ? 1 : 0);

function requireConfirm(args: Args, op: string): void {
  if (!args.confirm) {
    throw new ConfirmationRequired(`${op} requires confirm=true`);
  }
}

// ============================================================================
// DOMAIN
// ============================================================================

export const domain_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_list", args, async () => ctx.client().get("/api/v1/get/domain/all"));

export const domain_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_create", args, async () =>
    ctx.client().post("/api/v1/add/domain", {
      domain: args.domain,
      defquota: args.defquota_mb ?? 1024,
      maxquota: args.maxquota_mb ?? 10240,
      quota: args.quota_mb ?? 10240,
      mailboxes: args.mailboxes ?? 50,
      aliases: args.aliases ?? 100,
      relay_all_recipients: b(args.relay_all_recipients),
      backupmx: b(args.backupmx),
      active: b(args.active ?? true),
    }),
  );

export const domain_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_update", args, async () => {
    const attr: Record<string, unknown> = {};
    if ("defquota_mb" in args) attr.defquota = args.defquota_mb;
    if ("maxquota_mb" in args) attr.maxquota = args.maxquota_mb;
    if ("quota_mb" in args) attr.quota = args.quota_mb;
    if ("mailboxes" in args) attr.mailboxes = args.mailboxes;
    if ("aliases" in args) attr.aliases = args.aliases;
    if ("active" in args) attr.active = b(args.active);
    return ctx.client().post("/api/v1/edit/domain", { items: [args.domain], attr });
  });

export const domain_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "domain_delete");
  return ctx.audit.trace("domain_delete", args, async () =>
    ctx.client().post("/api/v1/delete/domain", [args.domain]),
  );
};

export const domain_set_footer = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_set_footer", args, async () => {
    const attr: Record<string, unknown> = {};
    if ("html" in args) attr.html = args.html;
    if ("plain" in args) attr.plain = args.plain;
    return ctx.client().post("/api/v1/edit/domain/footer", {
      items: [args.domain],
      attr,
    });
  });

export const domain_set_tags = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_set_tags", args, async () =>
    ctx.client().post("/api/v1/edit/domain", {
      items: [args.domain],
      attr: { tags: args.tags },
    }),
  );

export const domain_delete_tags = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_delete_tags", args, async () =>
    ctx.client().post(`/api/v1/delete/domain/tag/${args.domain}`, {}),
  );

// ============================================================================
// MAILBOX
// ============================================================================

export const mailbox_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_list", args, async () => {
    const data = await ctx.client().get("/api/v1/get/mailbox/all");
    if (Array.isArray(data) && args.domain) {
      return data.filter((m: { domain?: string }) => m.domain === args.domain);
    }
    return data;
  });

export const mailbox_list_by_domain = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_list_by_domain", args, async () =>
    ctx.client().get(`/api/v1/get/mailbox/all/${args.domain}`),
  );

export const mailbox_create = (ctx: AdminContext): Handler => async (args) => {
  const email = String(args.email);
  const [local, domain] = email.split("@");
  return ctx.audit.trace("mailbox_create", args, async () =>
    ctx.client().post("/api/v1/add/mailbox", {
      local_part: local,
      domain,
      name: args.name,
      quota: args.quota_mb ?? 1024,
      password: args.password,
      password2: args.password,
      active: b(args.active ?? true),
      force_pw_update: b(args.force_pw_update),
      tls_enforce_in: b(args.tls_enforce_in),
      tls_enforce_out: b(args.tls_enforce_out),
    }),
  );
};

export const mailbox_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_update", args, async () => {
    const attr: Record<string, unknown> = {};
    const map: [string, string][] = [
      ["name", "name"],
      ["quota_mb", "quota"],
      ["active", "active"],
      ["tls_enforce_in", "tls_enforce_in"],
      ["tls_enforce_out", "tls_enforce_out"],
      ["sogo_access", "sogo_access"],
      ["imap_access", "imap_access"],
      ["smtp_access", "smtp_access"],
      ["pop3_access", "pop3_access"],
    ];
    for (const [k, v] of map) {
      if (k in args) {
        const val = args[k];
        attr[v] = typeof val === "boolean" ? b(val) : val;
      }
    }
    return ctx.client().post("/api/v1/edit/mailbox", { items: [args.email], attr });
  });

export const mailbox_set_password = (ctx: AdminContext): Handler => async (args) => {
  // Resetting a mailbox password kicks the user out — destructive.
  requireConfirm(args, "mailbox_set_password");
  return ctx.audit.trace("mailbox_set_password", args, async () =>
    ctx.client().post("/api/v1/edit/mailbox", {
      items: [args.email],
      attr: { password: args.password, password2: args.password },
    }),
  );
};

export const mailbox_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "mailbox_delete");
  return ctx.audit.trace("mailbox_delete", args, async () =>
    ctx.client().post("/api/v1/delete/mailbox", [args.email]),
  );
};

export const mailbox_quota_report = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_quota_report", args, async () => {
    const threshold = Number(args.threshold_pct ?? 0);
    const data = await ctx.client().get("/api/v1/get/mailbox/all");
    const out: Array<{
      mailbox: string;
      quota_mb: number;
      used_mb: number;
      usage_pct: number;
    }> = [];
    if (Array.isArray(data)) {
      for (const m of data as Array<{ username: string; quota?: number; quota_used?: number }>) {
        const quota = Number(m.quota ?? 0);
        const used = Number(m.quota_used ?? 0);
        const pct = quota > 0 ? Math.round((100 * used) / quota * 10) / 10 : 0;
        if (pct >= threshold) {
          out.push({
            mailbox: m.username,
            quota_mb: Math.floor(quota / 1024 / 1024),
            used_mb: Math.floor(used / 1024 / 1024),
            usage_pct: pct,
          });
        }
      }
    }
    out.sort((a, b) => b.usage_pct - a.usage_pct);
    return out;
  });

export const mailbox_set_tags = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_set_tags", args, async () =>
    ctx.client().post("/api/v1/edit/mailbox", {
      items: [args.email],
      attr: { tags: args.tags },
    }),
  );

export const mailbox_delete_tags = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_delete_tags", args, async () =>
    ctx.client().post(`/api/v1/delete/mailbox/tag/${args.email}`, {}),
  );

export const mailbox_set_acl = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_set_acl", args, async () =>
    ctx.client().post("/api/v1/edit/user-acl", {
      items: [args.email],
      attr: { user_acl: args.acl },
    }),
  );

export const mailbox_set_custom_attribute = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("mailbox_set_custom_attribute", args, async () =>
    ctx.client().post("/api/v1/edit/mailbox/custom-attribute", {
      items: [args.email],
      attr: { attribute: args.attribute, value: args.value },
    }),
  );

// ============================================================================
// ALIAS
// ============================================================================

export const alias_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("alias_list", args, async () => {
    const data = await ctx.client().get("/api/v1/get/alias/all");
    if (Array.isArray(data) && args.domain) {
      return data.filter((a: { domain?: string }) => a.domain === args.domain);
    }
    return data;
  });

export const alias_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("alias_create", args, async () =>
    ctx.client().post("/api/v1/add/alias", {
      address: args.address,
      goto: args.goto,
      active: b(args.active ?? true),
      sogo_visible: b(args.sogo_visible ?? true),
      goto_null: b(args.goto_null),
      goto_spam: b(args.goto_spam),
      goto_ham: b(args.goto_ham),
    }),
  );

export const alias_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("alias_update", args, async () => {
    const aliases = (await ctx.client().get("/api/v1/get/alias/all")) as Array<{
      id: number;
      address: string;
    }>;
    const target = aliases.find((a) => a.address === args.address);
    if (!target) throw new Error(`alias '${args.address}' not found`);
    const attr: Record<string, unknown> = {};
    if ("goto" in args) attr.goto = args.goto;
    if ("active" in args) attr.active = b(args.active);
    return ctx.client().post("/api/v1/edit/alias", { items: [String(target.id)], attr });
  });

export const alias_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "alias_delete");
  return ctx.audit.trace("alias_delete", args, async () => {
    const aliases = (await ctx.client().get("/api/v1/get/alias/all")) as Array<{
      id: number;
      address: string;
    }>;
    const target = aliases.find((a) => a.address === args.address);
    if (!target) throw new Error(`alias '${args.address}' not found`);
    return ctx.client().post("/api/v1/delete/alias", [String(target.id)]);
  });
};

export const time_limited_alias_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("time_limited_alias_list", args, async () => {
    const path = args.mailbox
      ? `/api/v1/get/time_limited_aliases/${args.mailbox}`
      : "/api/v1/get/time_limited_aliases/all";
    return ctx.client().get(path);
  });

export const time_limited_alias_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("time_limited_alias_create", args, async () =>
    ctx.client().post("/api/v1/add/time_limited_alias", {
      address: args.address,
      goto: args.goto,
      validity: args.validity_days ?? 7,
    }),
  );

// ============================================================================
// APP PASSWORD
// ============================================================================

export const app_password_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("app_password_list", args, async () => {
    const data = await ctx.client().get(`/api/v1/get/app-passwd/all/${args.email}`);
    if (Array.isArray(data)) {
      return data.map((p: Record<string, unknown>) => ({
        ...p,
        password: "***",
      }));
    }
    return data;
  });

export const app_password_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("app_password_create", args, async () => {
    const protos = (args.protocols as string[] | undefined) ?? ["imap", "smtp"];
    const protocols = protos.map((p) => (p.endsWith("_access") ? p : `${p}_access`));
    return ctx.client().post("/api/v1/add/app-passwd", {
      username: args.email,
      app_name: args.app_name,
      app_passwd: args.password,
      app_passwd2: args.password,
      protocols,
      active: 1,
    });
  });

export const app_password_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "app_password_delete");
  return ctx.audit.trace("app_password_delete", args, async () =>
    ctx.client().post("/api/v1/delete/app-passwd", [String(args.id)]),
  );
};

// ============================================================================
// DKIM
// ============================================================================

export const dkim_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("dkim_list", args, async () =>
    ctx.client().get(args.domain ? `/api/v1/get/dkim/${args.domain}` : "/api/v1/get/dkim/all"),
  );

export const dkim_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("dkim_create", args, async () =>
    ctx.client().post("/api/v1/add/dkim", {
      dkim_selector: args.selector ?? "dkim",
      domains: args.domain,
      key_size: args.key_size_bits ?? 2048,
    }),
  );

export const dkim_duplicate = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("dkim_duplicate", args, async () =>
    ctx.client().post("/api/v1/add/dkim_duplicate", {
      from_domain: args.from_domain,
      to_domain: args.to_domain,
    }),
  );

export const dkim_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "dkim_delete");
  return ctx.audit.trace("dkim_delete", args, async () =>
    ctx.client().post("/api/v1/delete/dkim", [args.domain]),
  );
};

// ============================================================================
// STATUS
// ============================================================================

export const server_version = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("server_version", args, async () => ctx.client().get("/api/v1/get/status/version"));

export const server_containers_status = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("server_containers_status", args, async () =>
    ctx.client().get("/api/v1/get/status/containers"),
  );

export const server_vmail_status = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("server_vmail_status", args, async () =>
    ctx.client().get("/api/v1/get/status/vmail"),
  );

export const server_status_summary = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("server_status_summary", args, async () => {
    const c = ctx.client();
    const safeGet = async (path: string) => {
      try {
        return await c.get(path);
      } catch {
        return null;
      }
    };
    const [version, containers, vmail, queue, fail2ban] = await Promise.all([
      c.get("/api/v1/get/status/version"),
      c.get("/api/v1/get/status/containers"),
      c.get("/api/v1/get/status/vmail"),
      safeGet("/api/v1/get/mailq/all"),
      safeGet("/api/v1/get/fail2ban"),
    ]);
    type Container = { state?: string; status?: string };
    const containersDict = (containers ?? {}) as Record<string, Container>;
    const values = Object.values(containersDict);
    const running = values.filter((v) => v?.state === "running").length;
    const healthy = values.filter(
      (v) => v?.state === "running" && (v?.status ?? "").startsWith("healthy"),
    ).length;
    const down = values.filter((v) => v?.state && v.state !== "running").length;

    let vmailPct: number | null = null;
    if (vmail && typeof vmail === "object" && "used_percent" in vmail) {
      const raw = String((vmail as { used_percent: unknown }).used_percent).replace("%", "");
      const parsed = Number.parseFloat(raw);
      vmailPct = Number.isNaN(parsed) ? null : parsed;
    }

    const fail2banObj = fail2ban as { active_bans?: unknown[] } | null;

    return {
      version,
      containers_total: Object.keys(containersDict).length,
      containers_running: running,
      containers_healthy: healthy,
      containers_down: down,
      vmail,
      vmail_disk_pct: vmailPct,
      queue_length: Array.isArray(queue) ? queue.length : null,
      fail2ban_bans: Array.isArray(fail2banObj?.active_bans)
        ? fail2banObj!.active_bans!.length
        : null,
    };
  });

// ============================================================================
// BCC, RECIPIENT MAP, TRANSPORT, RELAYHOST, TLS, FORWARD HOST
// ============================================================================

export const bcc_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("bcc_list", args, async () => ctx.client().get("/api/v1/get/bcc/all"));

export const bcc_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("bcc_create", args, async () =>
    ctx.client().post("/api/v1/add/bcc", {
      local_dest: args.local_dest,
      bcc_dest: args.bcc_dest,
      type: args.type,
      active: b(args.active ?? true),
    }),
  );

export const bcc_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "bcc_delete");
  return ctx.audit.trace("bcc_delete", args, async () =>
    ctx.client().post("/api/v1/delete/bcc", [String(args.id)]),
  );
};

export const recipient_map_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("recipient_map_list", args, async () =>
    ctx.client().get("/api/v1/get/recipient_map/all"),
  );

export const recipient_map_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("recipient_map_create", args, async () =>
    ctx.client().post("/api/v1/add/recipient_map", {
      recipient_map_old: args.old_dest,
      recipient_map_new: args.new_dest,
      active: b(args.active ?? true),
    }),
  );

export const recipient_map_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "recipient_map_delete");
  return ctx.audit.trace("recipient_map_delete", args, async () =>
    ctx.client().post("/api/v1/delete/recipient_map", [String(args.id)]),
  );
};

export const transport_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("transport_list", args, async () => ctx.client().get("/api/v1/get/transport/all"));

export const transport_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("transport_create", args, async () =>
    ctx.client().post("/api/v1/add/transport", {
      destination: args.destination,
      nexthop: args.nexthop,
      username: args.username ?? "",
      password: args.password ?? "",
      active: b(args.active ?? true),
    }),
  );

export const transport_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "transport_delete"); // mail routing-critical
  return ctx.audit.trace("transport_delete", args, async () =>
    ctx.client().post("/api/v1/delete/transport", [String(args.id)]),
  );
};

export const relayhost_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("relayhost_list", args, async () => ctx.client().get("/api/v1/get/relayhost/all"));

export const relayhost_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("relayhost_create", args, async () =>
    ctx.client().post("/api/v1/add/relayhost", {
      hostname: args.hostname,
      username: args.username ?? "",
      password: args.password ?? "",
      active: b(args.active ?? true),
    }),
  );

export const relayhost_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "relayhost_delete"); // mail routing-critical
  return ctx.audit.trace("relayhost_delete", args, async () =>
    ctx.client().post("/api/v1/delete/relayhost", [String(args.id)]),
  );
};

export const tls_policy_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("tls_policy_list", args, async () =>
    ctx.client().get("/api/v1/get/tls-policy-map/all"),
  );

export const tls_policy_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("tls_policy_create", args, async () =>
    ctx.client().post("/api/v1/add/tls-policy-map", {
      dest: args.dest,
      policy: args.policy,
      parameters: args.parameters ?? "",
      active: b(args.active ?? true),
    }),
  );

export const tls_policy_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "tls_policy_delete");
  return ctx.audit.trace("tls_policy_delete", args, async () =>
    ctx.client().post("/api/v1/delete/tls-policy-map", [String(args.id)]),
  );
};

export const forward_host_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("forward_host_list", args, async () => ctx.client().get("/api/v1/get/fwdhost/all"));

export const forward_host_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("forward_host_create", args, async () =>
    ctx.client().post("/api/v1/add/fwdhost", {
      hostname: args.hostname,
      filter_spam: b(args.filter_spam),
      keep_spam: b(args.keep_spam),
    }),
  );

export const forward_host_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "forward_host_delete");
  return ctx.audit.trace("forward_host_delete", args, async () =>
    ctx.client().post("/api/v1/delete/fwdhost", [args.hostname]),
  );
};

// ============================================================================
// SYNC JOBS
// ============================================================================

export const sync_job_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("sync_job_list", args, async () => {
    const data = await ctx.client().get("/api/v1/get/syncjobs/all/no_log");
    if (Array.isArray(data) && args.mailbox) {
      return data.filter((j: { user2?: string }) => j.user2 === args.mailbox);
    }
    return data;
  });

export const sync_job_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("sync_job_create", args, async () =>
    ctx.client().post("/api/v1/add/syncjob", {
      username: args.mailbox,
      host1: args.host,
      port1: String(args.port ?? 993),
      enc1: args.enc ?? "TLS",
      user1: args.user,
      password1: args.password,
      mins_interval: args.mins_interval ?? 20,
      maxage: args.maxage_days ?? 0,
      maxbytespersecond: args.maxbytespersecond ?? 0,
      timeout1: args.timeout1 ?? 600,
      timeout2: args.timeout2 ?? 600,
      delete2duplicates: b(args.delete2duplicates ?? true),
      delete1: b(args.delete1),
      delete2: b(args.delete2),
      automap: b(args.automap ?? true),
      skipcrossduplicates: b(args.skipcrossduplicates),
      subfolder2: args.subfolder2 ?? "",
      exclude: args.exclude ?? "",
      custom_params: args.custom_params ?? "",
      subscribeall: b(args.subscribeall),
      active: b(args.active ?? true),
    }),
  );

export const sync_job_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("sync_job_update", args, async () => {
    const attr: Record<string, unknown> = {};
    if ("mins_interval" in args) attr.mins_interval = args.mins_interval;
    if ("active" in args) attr.active = b(args.active);
    if ("password" in args) attr.password1 = args.password;
    return ctx.client().post("/api/v1/edit/syncjob", { items: [String(args.id)], attr });
  });

export const sync_job_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "sync_job_delete");
  return ctx.audit.trace("sync_job_delete", args, async () =>
    ctx.client().post("/api/v1/delete/syncjob", [String(args.id)]),
  );
};

// ============================================================================
// RESOURCES, OAUTH2, DOMAIN ADMINS, DOMAIN POLICIES
// ============================================================================

export const resource_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("resource_list", args, async () => ctx.client().get("/api/v1/get/resource/all"));

export const resource_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("resource_create", args, async () => {
    const mb = args.multiple_bookings ?? 0;
    return ctx.client().post("/api/v1/add/resource", {
      name: args.name,
      domain: args.domain,
      description: args.description ?? "",
      kind: args.kind ?? "location",
      multiple_bookings_select: mb ? "custom" : "0",
      multiple_bookings_custom: mb,
      multiple_bookings: mb,
      active: b(args.active ?? true),
    });
  });

export const resource_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "resource_delete");
  return ctx.audit.trace("resource_delete", args, async () =>
    ctx.client().post("/api/v1/delete/resource", [args.name]),
  );
};

export const oauth2_client_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("oauth2_client_list", args, async () =>
    ctx.client().get("/api/v1/get/oauth2-client/all"),
  );

export const oauth2_client_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("oauth2_client_create", args, async () =>
    ctx.client().post("/api/v1/add/oauth2-client", {
      redirect_uri: args.redirect_uri,
      grant_types: args.grant_types ?? "authorization_code refresh_token",
      scope: args.scope ?? "profile",
    }),
  );

export const oauth2_client_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "oauth2_client_delete"); // breaks integrations
  return ctx.audit.trace("oauth2_client_delete", args, async () =>
    ctx.client().post("/api/v1/delete/oauth2-client", [String(args.id)]),
  );
};

export const domain_admin_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_admin_list", args, async () =>
    ctx.client().get("/api/v1/get/domain-admin/all"),
  );

export const domain_admin_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_admin_create", args, async () =>
    ctx.client().post("/api/v1/add/domain-admin", {
      username: args.username,
      domains: Array.isArray(args.domains) ? args.domains.join(",") : args.domains,
      password: args.password,
      password2: args.password,
      active: b(args.active ?? true),
    }),
  );

export const domain_admin_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_admin_update", args, async () => {
    const attr: Record<string, unknown> = {};
    if ("domains" in args)
      attr.domains = Array.isArray(args.domains) ? args.domains.join(",") : args.domains;
    if ("password" in args) {
      attr.password = args.password;
      attr.password2 = args.password;
    }
    if ("active" in args) attr.active = b(args.active);
    return ctx.client().post("/api/v1/edit/domain-admin", { items: [args.username], attr });
  });

export const domain_admin_set_acl = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_admin_set_acl", args, async () =>
    ctx.client().post("/api/v1/edit/da-acl", {
      items: [args.username],
      attr: { domain_admin_acl: args.acl },
    }),
  );

export const domain_admin_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "domain_admin_delete");
  return ctx.audit.trace("domain_admin_delete", args, async () =>
    ctx.client().post("/api/v1/delete/domain-admin", [args.username]),
  );
};

export const domain_admin_sso_token = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_admin_sso_token", args, async () =>
    ctx.client().post("/api/v1/add/sso/domain-admin", { username: args.username }),
  );

export const domain_policy_list_blacklist = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_policy_list_blacklist", args, async () =>
    ctx.client().get(`/api/v1/get/policy_bl_domain/${args.domain}`),
  );

export const domain_policy_list_whitelist = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_policy_list_whitelist", args, async () =>
    ctx.client().get(`/api/v1/get/policy_wl_domain/${args.domain}`),
  );

export const domain_policy_create = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("domain_policy_create", args, async () =>
    ctx.client().post("/api/v1/add/domain-policy", {
      domain: args.domain,
      object_list: args.object_list,
      object_from: args.object_from,
    }),
  );

export const domain_policy_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "domain_policy_delete");
  return ctx.audit.trace("domain_policy_delete", args, async () =>
    ctx.client().post("/api/v1/delete/domain-policy", [String(args.id)]),
  );
};

// ============================================================================
// QUARANTINE, QUEUE, FAIL2BAN, RATELIMIT, SPAM, SETTINGS, LOGS
// ============================================================================

export const quarantine_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("quarantine_list", args, async () => ctx.client().get("/api/v1/get/quarantine/all"));

export const quarantine_release = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("quarantine_release", args, async () =>
    ctx.client().post("/api/v1/edit/qitem", {
      items: ((args.ids as Array<number | string>) ?? []).map(String),
      attr: { action: "release" },
    }),
  );

export const quarantine_learn_spam = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("quarantine_learn_spam", args, async () =>
    ctx.client().post("/api/v1/edit/qitem", {
      items: ((args.ids as Array<number | string>) ?? []).map(String),
      attr: { action: "learnspam" },
    }),
  );

export const quarantine_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "quarantine_delete");
  return ctx.audit.trace("quarantine_delete", args, async () =>
    ctx.client().post(
      "/api/v1/delete/qitem",
      ((args.ids as Array<number | string>) ?? []).map(String),
    ),
  );
};

export const quarantine_set_notification = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("quarantine_set_notification", args, async () => {
    const attr = Object.fromEntries(Object.entries(args).filter(([k]) => k !== "items"));
    return ctx.client().post("/api/v1/edit/quarantine_notification", {
      items: ["all"],
      attr,
    });
  });

export const queue_list = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("queue_list", args, async () => ctx.client().get("/api/v1/get/mailq/all"));

export const queue_flush = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("queue_flush", args, async () =>
    ctx.client().post("/api/v1/edit/mailq", { items: ["flush"] }),
  );

export const queue_delete = (ctx: AdminContext): Handler => async (args) => {
  requireConfirm(args, "queue_delete");
  return ctx.audit.trace("queue_delete", args, async () =>
    ctx.client().post("/api/v1/delete/mailq", args.queue_ids),
  );
};

export const fail2ban_get = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("fail2ban_get", args, async () => ctx.client().get("/api/v1/get/fail2ban"));

export const fail2ban_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("fail2ban_update", args, async () => {
    const attr: Record<string, unknown> = {};
    for (const k of [
      "ban_time",
      "max_attempts",
      "retry_window",
      "whitelist",
      "blacklist",
      "manage_external",
    ]) {
      if (k in args) attr[k] = args[k];
    }
    return ctx.client().post("/api/v1/edit/fail2ban", { items: ["none"], attr });
  });

export const fail2ban_unban = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("fail2ban_unban", args, async () =>
    ctx.client().post("/api/v1/edit/fail2ban", {
      items: ["none"],
      attr: { action: "unban", network: args.ip },
    }),
  );

export const ratelimit_get_mailbox = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("ratelimit_get_mailbox", args, async () =>
    ctx.client().get(`/api/v1/get/rl-mbox/${args.email}`),
  );

export const ratelimit_set_mailbox = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("ratelimit_set_mailbox", args, async () =>
    ctx.client().post("/api/v1/edit/rl-mbox/", {
      items: [args.email],
      attr: { rl_value: args.value, rl_frame: args.frame },
    }),
  );

export const ratelimit_get_domain = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("ratelimit_get_domain", args, async () =>
    ctx.client().get(`/api/v1/get/rl-domain/${args.domain}`),
  );

export const ratelimit_set_domain = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("ratelimit_set_domain", args, async () =>
    ctx.client().post("/api/v1/edit/rl-domain/", {
      items: [args.domain],
      attr: { rl_value: args.value, rl_frame: args.frame },
    }),
  );

export const spam_score_get = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("spam_score_get", args, async () =>
    ctx.client().get(`/api/v1/get/spam-score/${args.email ?? "all"}`),
  );

export const spam_score_set = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("spam_score_set", args, async () =>
    ctx.client().post("/api/v1/edit/spam-score/", {
      items: [args.email],
      attr: { spam_score: `${args.low_score},${args.high_score}` },
    }),
  );

export const cors_settings_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("cors_settings_update", args, async () => {
    const attr: Record<string, unknown> = {};
    if ("allowed_origins" in args) attr.allowed_origins = args.allowed_origins;
    if ("allowed_methods" in args) attr.allowed_methods = args.allowed_methods;
    return ctx.client().post("/api/v1/edit/cors", { attr });
  });

export const identity_provider_settings_update = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("identity_provider_settings_update", args, async () =>
    ctx.client().post("/api/v1/edit/identity-provider", args),
  );

export const pushover_set = (ctx: AdminContext): Handler => async (args) =>
  ctx.audit.trace("pushover_set", args, async () => {
    const attr = Object.fromEntries(Object.entries(args).filter(([k]) => k !== "email"));
    if ("active" in attr) attr.active = b(attr.active);
    return ctx.client().post("/api/v1/edit/pushover", { items: [args.email], attr });
  });

// Logs
function logsFactory(actionName: string, mcPath: string) {
  return (ctx: AdminContext): Handler =>
    async (args) =>
      ctx.audit.trace(actionName, args, async () => {
        const lines = Math.min(Number(args.lines ?? 100), 5000);
        return ctx.client().get(`/api/v1/get/logs/${mcPath}/${lines}`);
      });
}

export const logs_get_postfix = logsFactory("logs_get_postfix", "postfix");
export const logs_get_dovecot = logsFactory("logs_get_dovecot", "dovecot");
export const logs_get_rspamd = logsFactory("logs_get_rspamd", "rspamd-history");
export const logs_get_sogo = logsFactory("logs_get_sogo", "sogo");
export const logs_get_acme = logsFactory("logs_get_acme", "acme");
export const logs_get_netfilter = logsFactory("logs_get_netfilter", "netfilter");
export const logs_get_watchdog = logsFactory("logs_get_watchdog", "watchdog");
export const logs_get_api = logsFactory("logs_get_api", "api");
export const logs_get_autodiscover = logsFactory("logs_get_autodiscover", "autodiscover");
export const logs_get_ratelimit = logsFactory("logs_get_ratelimit", "ratelimited");

// send_test_mail — not portable to Node without docker exec; stub for now.
export const send_test_mail = (_ctx: AdminContext): Handler => async () => {
  throw new Error(
    "send_test_mail is only available when the MCP runs on the Mailcow host with docker access. Use the Python implementation if you need this.",
  );
};
