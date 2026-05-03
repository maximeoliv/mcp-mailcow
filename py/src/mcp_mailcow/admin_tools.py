"""Admin-mode tool implementations (Mailcow REST API).

Pattern: each tool is a factory `tool_name(ctx) -> ToolHandler` that captures
the AdminContext (config + audit + client) and returns an async callable.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from .audit import AuditLogger
from .config import AdminConfig
from .exceptions import ConfirmationRequired
from .mailcow_api import MailcowClient

ToolHandler = Callable[[dict[str, Any]], Awaitable[Any]]


@dataclass
class AdminContext:
    config: AdminConfig
    audit: AuditLogger

    def client(self) -> MailcowClient:
        return MailcowClient(
            base_url=self.config.base_url,
            api_key=self.config.api_key,
            tls_verify=self.config.tls_verify,
        )


def _b(v: Any) -> int:
    """Bool → 0/1 (Mailcow API style)."""
    return int(bool(v))


def _require_confirm(args: dict[str, Any], op: str) -> None:
    if not args.get("confirm"):
        raise ConfirmationRequired(f"{op} requires confirm=true")


# =============================================================================
# DOMAIN
# =============================================================================

def domain_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/domain/all")
    return h


def domain_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_create", args):
            payload = {
                "domain": args["domain"],
                "defquota": args.get("defquota_mb", 1024),
                "maxquota": args.get("maxquota_mb", 10240),
                "quota": args.get("quota_mb", 10240),
                "mailboxes": args.get("mailboxes", 50),
                "aliases": args.get("aliases", 100),
                "relay_all_recipients": _b(args.get("relay_all_recipients", False)),
                "backupmx": _b(args.get("backupmx", False)),
                "active": _b(args.get("active", True)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/domain", payload)
    return h


def domain_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_update", args):
            attr: dict[str, Any] = {}
            if "defquota_mb" in args: attr["defquota"] = args["defquota_mb"]
            if "maxquota_mb" in args: attr["maxquota"] = args["maxquota_mb"]
            if "quota_mb" in args: attr["quota"] = args["quota_mb"]
            if "mailboxes" in args: attr["mailboxes"] = args["mailboxes"]
            if "aliases" in args: attr["aliases"] = args["aliases"]
            if "active" in args: attr["active"] = _b(args["active"])
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/domain", {"items": [args["domain"]], "attr": attr})
    return h


def domain_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "domain_delete")
        with ctx.audit.trace("domain_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/domain", [args["domain"]])
    return h


def domain_set_footer(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_set_footer", args):
            attr = {}
            if "html" in args: attr["html"] = args["html"]
            if "plain" in args: attr["plain"] = args["plain"]
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/domain/footer",
                    {"items": [args["domain"]], "attr": attr},
                )
    return h


def domain_set_tags(ctx: AdminContext) -> ToolHandler:
    """Set tags on a domain — done via the standard edit/domain endpoint."""
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_set_tags", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/domain",
                    {"items": [args["domain"]], "attr": {"tags": args["tags"]}},
                )
    return h


def domain_delete_tags(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_delete_tags", args):
            async with ctx.client() as c:
                return await c.post(f"/api/v1/delete/domain/tag/{args['domain']}", {})
    return h


# =============================================================================
# MAILBOX
# =============================================================================

def mailbox_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_list", args):
            async with ctx.client() as c:
                data = await c.get("/api/v1/get/mailbox/all")
                if isinstance(data, list) and args.get("domain"):
                    data = [m for m in data if m.get("domain") == args["domain"]]
                return data
    return h


def mailbox_list_by_domain(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_list_by_domain", args):
            async with ctx.client() as c:
                return await c.get(f"/api/v1/get/mailbox/all/{args['domain']}")
    return h


def mailbox_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        local, _, domain = args["email"].partition("@")
        with ctx.audit.trace("mailbox_create", args):
            payload = {
                "local_part": local,
                "domain": domain,
                "name": args["name"],
                "quota": args.get("quota_mb", 1024),
                "password": args["password"],
                "password2": args["password"],
                "active": _b(args.get("active", True)),
                "force_pw_update": _b(args.get("force_pw_update", False)),
                "tls_enforce_in": _b(args.get("tls_enforce_in", False)),
                "tls_enforce_out": _b(args.get("tls_enforce_out", False)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/mailbox", payload)
    return h


def mailbox_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_update", args):
            attr: dict[str, Any] = {}
            for k_in, k_api in [
                ("name", "name"), ("quota_mb", "quota"), ("active", "active"),
                ("tls_enforce_in", "tls_enforce_in"), ("tls_enforce_out", "tls_enforce_out"),
                ("sogo_access", "sogo_access"), ("imap_access", "imap_access"),
                ("smtp_access", "smtp_access"), ("pop3_access", "pop3_access"),
            ]:
                if k_in in args:
                    v = args[k_in]
                    attr[k_api] = _b(v) if isinstance(v, bool) else v
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/mailbox", {"items": [args["email"]], "attr": attr})
    return h


def mailbox_set_password(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        # Resetting a mailbox password kicks the user out and is destructive
        # (loss of access). Require explicit confirm.
        _require_confirm(args, "mailbox_set_password")
        with ctx.audit.trace("mailbox_set_password", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/mailbox",
                    {"items": [args["email"]], "attr": {"password": args["password"], "password2": args["password"]}},
                )
    return h


def mailbox_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "mailbox_delete")
        with ctx.audit.trace("mailbox_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/mailbox", [args["email"]])
    return h


def mailbox_quota_report(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_quota_report", args):
            threshold = int(args.get("threshold_pct", 0))
            async with ctx.client() as c:
                data = await c.get("/api/v1/get/mailbox/all")
            out = []
            for m in data if isinstance(data, list) else []:
                quota = int(m.get("quota", 0))
                used = int(m.get("quota_used", 0))
                pct = round(100 * used / quota, 1) if quota > 0 else 0.0
                if pct >= threshold:
                    out.append({
                        "mailbox": m["username"],
                        "quota_mb": quota // 1024 // 1024,
                        "used_mb": used // 1024 // 1024,
                        "usage_pct": pct,
                    })
            out.sort(key=lambda r: r["usage_pct"], reverse=True)
            return out
    return h


def mailbox_set_tags(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_set_tags", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/mailbox",
                    {"items": [args["email"]], "attr": {"tags": args["tags"]}},
                )
    return h


def mailbox_delete_tags(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_delete_tags", args):
            async with ctx.client() as c:
                return await c.post(f"/api/v1/delete/mailbox/tag/{args['email']}", {})
    return h


def mailbox_set_acl(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_set_acl", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/user-acl",
                    {"items": [args["email"]], "attr": {"user_acl": args["acl"]}},
                )
    return h


def mailbox_set_custom_attribute(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("mailbox_set_custom_attribute", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/mailbox/custom-attribute",
                    {
                        "items": [args["email"]],
                        "attr": {"attribute": args["attribute"], "value": args["value"]},
                    },
                )
    return h


# =============================================================================
# ALIAS
# =============================================================================

def alias_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("alias_list", args):
            async with ctx.client() as c:
                data = await c.get("/api/v1/get/alias/all")
                if isinstance(data, list) and args.get("domain"):
                    data = [a for a in data if a.get("domain") == args["domain"]]
                return data
    return h


def alias_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("alias_create", args):
            payload = {
                "address": args["address"],
                "goto": args["goto"],
                "active": _b(args.get("active", True)),
                "sogo_visible": _b(args.get("sogo_visible", True)),
                "goto_null": _b(args.get("goto_null", False)),
                "goto_spam": _b(args.get("goto_spam", False)),
                "goto_ham": _b(args.get("goto_ham", False)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/alias", payload)
    return h


def alias_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("alias_update", args):
            async with ctx.client() as c:
                # Find ID from address
                aliases = await c.get("/api/v1/get/alias/all")
                target = next((a for a in aliases if a.get("address") == args["address"]), None)
                if not target:
                    raise RuntimeError(f"alias '{args['address']}' not found")
                attr: dict[str, Any] = {}
                if "goto" in args: attr["goto"] = args["goto"]
                if "active" in args: attr["active"] = _b(args["active"])
                return await c.post(
                    "/api/v1/edit/alias",
                    {"items": [str(target["id"])], "attr": attr},
                )
    return h


def alias_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "alias_delete")
        with ctx.audit.trace("alias_delete", args):
            async with ctx.client() as c:
                aliases = await c.get("/api/v1/get/alias/all")
                target = next((a for a in aliases if a.get("address") == args["address"]), None)
                if not target:
                    raise RuntimeError(f"alias '{args['address']}' not found")
                return await c.post("/api/v1/delete/alias", [str(target["id"])])
    return h


def time_limited_alias_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("time_limited_alias_list", args):
            async with ctx.client() as c:
                # Mailcow expects a mailbox parameter for this endpoint
                if "mailbox" in args:
                    return await c.get(f"/api/v1/get/time_limited_aliases/{args['mailbox']}")
                else:
                    return await c.get("/api/v1/get/time_limited_aliases/all")
    return h


def time_limited_alias_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("time_limited_alias_create", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/add/time_limited_alias",
                    {
                        "address": args["address"],
                        "goto": args["goto"],
                        "validity": args.get("validity_days", 7),
                    },
                )
    return h


# =============================================================================
# APP_PASSWORD
# =============================================================================

def app_password_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("app_password_list", args):
            async with ctx.client() as c:
                data = await c.get(f"/api/v1/get/app-passwd/all/{args['email']}")
            if isinstance(data, list):
                for p in data:
                    if "password" in p:
                        p["password"] = "***"  # never expose hashed password
            return data
    return h


def app_password_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("app_password_create", args):
            protocols = [
                f"{p}_access" if not p.endswith("_access") else p
                for p in args.get("protocols", ["imap", "smtp"])
            ]
            payload = {
                "username": args["email"],
                "app_name": args["app_name"],
                "app_passwd": args["password"],
                "app_passwd2": args["password"],
                "protocols": protocols,
                "active": 1,
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/app-passwd", payload)
    return h


def app_password_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "app_password_delete")
        with ctx.audit.trace("app_password_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/app-passwd", [str(args["id"])])
    return h


# =============================================================================
# DKIM
# =============================================================================

def dkim_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("dkim_list", args):
            async with ctx.client() as c:
                if "domain" in args:
                    return await c.get(f"/api/v1/get/dkim/{args['domain']}")
                return await c.get("/api/v1/get/dkim/all")
    return h


def dkim_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("dkim_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/dkim", {
                    "dkim_selector": args.get("selector", "dkim"),
                    "domains": args["domain"],
                    "key_size": args.get("key_size_bits", 2048),
                })
    return h


def dkim_duplicate(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("dkim_duplicate", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/dkim_duplicate", {
                    "from_domain": args["from_domain"],
                    "to_domain": args["to_domain"],
                })
    return h


def dkim_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "dkim_delete")
        with ctx.audit.trace("dkim_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/dkim", [args["domain"]])
    return h


# =============================================================================
# BCC
# =============================================================================

def bcc_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("bcc_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/bcc/all")
    return h


def bcc_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("bcc_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/bcc", {
                    "local_dest": args["local_dest"],
                    "bcc_dest": args["bcc_dest"],
                    "type": args["type"],
                    "active": _b(args.get("active", True)),
                })
    return h


def bcc_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "bcc_delete")
        with ctx.audit.trace("bcc_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/bcc", [str(args["id"])])
    return h


# =============================================================================
# RECIPIENT MAP
# =============================================================================

def recipient_map_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("recipient_map_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/recipient_map/all")
    return h


def recipient_map_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("recipient_map_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/recipient_map", {
                    "recipient_map_old": args["old_dest"],
                    "recipient_map_new": args["new_dest"],
                    "active": _b(args.get("active", True)),
                })
    return h


def recipient_map_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "recipient_map_delete")
        with ctx.audit.trace("recipient_map_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/recipient_map", [str(args["id"])])
    return h


# =============================================================================
# TRANSPORT (destination-based)
# =============================================================================

def transport_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("transport_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/transport/all")
    return h


def transport_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("transport_create", args):
            payload = {
                "destination": args["destination"],
                "nexthop": args["nexthop"],
                "username": args.get("username", ""),
                "password": args.get("password", ""),
                "active": _b(args.get("active", True)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/transport", payload)
    return h


def transport_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "transport_delete")  # mail routing-critical
        with ctx.audit.trace("transport_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/transport", [str(args["id"])])
    return h


# =============================================================================
# RELAYHOST (sender-dependent transport)
# =============================================================================

def relayhost_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("relayhost_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/relayhost/all")
    return h


def relayhost_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("relayhost_create", args):
            payload = {
                "hostname": args["hostname"],
                "username": args.get("username", ""),
                "password": args.get("password", ""),
                "active": _b(args.get("active", True)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/relayhost", payload)
    return h


def relayhost_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "relayhost_delete")  # mail routing-critical
        with ctx.audit.trace("relayhost_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/relayhost", [str(args["id"])])
    return h


# =============================================================================
# TLS POLICY
# =============================================================================

def tls_policy_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("tls_policy_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/tls-policy-map/all")
    return h


def tls_policy_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("tls_policy_create", args):
            payload = {
                "dest": args["dest"],
                "policy": args["policy"],
                "parameters": args.get("parameters", ""),
                "active": _b(args.get("active", True)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/tls-policy-map", payload)
    return h


def tls_policy_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "tls_policy_delete")
        with ctx.audit.trace("tls_policy_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/tls-policy-map", [str(args["id"])])
    return h


# =============================================================================
# FORWARD HOSTS
# =============================================================================

def forward_host_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("forward_host_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/fwdhost/all")
    return h


def forward_host_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("forward_host_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/fwdhost", {
                    "hostname": args["hostname"],
                    "filter_spam": _b(args.get("filter_spam", False)),
                    "keep_spam": _b(args.get("keep_spam", False)),
                })
    return h


def forward_host_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "forward_host_delete")
        with ctx.audit.trace("forward_host_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/fwdhost", [args["hostname"]])
    return h


# =============================================================================
# SYNC JOBS
# =============================================================================

def sync_job_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("sync_job_list", args):
            async with ctx.client() as c:
                data = await c.get("/api/v1/get/syncjobs/all/no_log")
                if isinstance(data, list) and args.get("mailbox"):
                    data = [j for j in data if j.get("user2") == args["mailbox"]]
                return data
    return h


def sync_job_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("sync_job_create", args):
            payload = {
                "username": args["mailbox"],
                "host1": args["host"],
                "port1": str(args.get("port", 993)),
                "enc1": args.get("enc", "TLS"),
                "user1": args["user"],
                "password1": args["password"],
                "mins_interval": args.get("mins_interval", 20),
                "maxage": args.get("maxage_days", 0),
                "maxbytespersecond": args.get("maxbytespersecond", 0),
                "timeout1": args.get("timeout1", 600),
                "timeout2": args.get("timeout2", 600),
                "delete2duplicates": _b(args.get("delete2duplicates", True)),
                "delete1": _b(args.get("delete1", False)),
                "delete2": _b(args.get("delete2", False)),
                "automap": _b(args.get("automap", True)),
                "skipcrossduplicates": _b(args.get("skipcrossduplicates", False)),
                "subfolder2": args.get("subfolder2", ""),
                "exclude": args.get("exclude", ""),
                "custom_params": args.get("custom_params", ""),
                "subscribeall": _b(args.get("subscribeall", False)),
                "active": _b(args.get("active", True)),
            }
            async with ctx.client() as c:
                return await c.post("/api/v1/add/syncjob", payload)
    return h


def sync_job_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("sync_job_update", args):
            attr: dict[str, Any] = {}
            if "mins_interval" in args: attr["mins_interval"] = args["mins_interval"]
            if "active" in args: attr["active"] = _b(args["active"])
            if "password" in args: attr["password1"] = args["password"]
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/syncjob", {"items": [str(args["id"])], "attr": attr})
    return h


def sync_job_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "sync_job_delete")
        with ctx.audit.trace("sync_job_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/syncjob", [str(args["id"])])
    return h


# =============================================================================
# RESOURCES
# =============================================================================

def resource_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("resource_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/resource/all")
    return h


def resource_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("resource_create", args):
            mb = args.get("multiple_bookings", 0)
            async with ctx.client() as c:
                return await c.post("/api/v1/add/resource", {
                    "name": args["name"],
                    "domain": args["domain"],
                    "description": args.get("description", ""),
                    "kind": args.get("kind", "location"),
                    "multiple_bookings_select": "custom" if mb else "0",
                    "multiple_bookings_custom": mb,
                    "multiple_bookings": mb,
                    "active": _b(args.get("active", True)),
                })
    return h


def resource_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "resource_delete")
        with ctx.audit.trace("resource_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/resource", [args["name"]])
    return h


# =============================================================================
# OAUTH2
# =============================================================================

def oauth2_client_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("oauth2_client_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/oauth2-client/all")
    return h


def oauth2_client_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("oauth2_client_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/oauth2-client", {
                    "redirect_uri": args["redirect_uri"],
                    "grant_types": args.get("grant_types", "authorization_code refresh_token"),
                    "scope": args.get("scope", "profile"),
                })
    return h


def oauth2_client_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "oauth2_client_delete")  # breaks integrations
        with ctx.audit.trace("oauth2_client_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/oauth2-client", [str(args["id"])])
    return h


# =============================================================================
# DOMAIN ADMIN
# =============================================================================

def domain_admin_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_admin_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/domain-admin/all")
    return h


def domain_admin_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_admin_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/domain-admin", {
                    "username": args["username"],
                    "domains": ",".join(args["domains"]) if isinstance(args["domains"], list) else args["domains"],
                    "password": args["password"],
                    "password2": args["password"],
                    "active": _b(args.get("active", True)),
                })
    return h


def domain_admin_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_admin_update", args):
            attr: dict[str, Any] = {}
            if "domains" in args:
                attr["domains"] = ",".join(args["domains"]) if isinstance(args["domains"], list) else args["domains"]
            if "password" in args:
                attr["password"] = args["password"]
                attr["password2"] = args["password"]
            if "active" in args: attr["active"] = _b(args["active"])
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/domain-admin", {"items": [args["username"]], "attr": attr})
    return h


def domain_admin_set_acl(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_admin_set_acl", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/da-acl",
                    {"items": [args["username"]], "attr": {"domain_admin_acl": args["acl"]}},
                )
    return h


def domain_admin_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "domain_admin_delete")
        with ctx.audit.trace("domain_admin_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/domain-admin", [args["username"]])
    return h


def domain_admin_sso_token(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_admin_sso_token", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/sso/domain-admin", {"username": args["username"]})
    return h


# =============================================================================
# DOMAIN POLICY
# =============================================================================

def domain_policy_list_blacklist(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_policy_list_blacklist", args):
            async with ctx.client() as c:
                return await c.get(f"/api/v1/get/policy_bl_domain/{args['domain']}")
    return h


def domain_policy_list_whitelist(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_policy_list_whitelist", args):
            async with ctx.client() as c:
                return await c.get(f"/api/v1/get/policy_wl_domain/{args['domain']}")
    return h


def domain_policy_create(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("domain_policy_create", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/add/domain-policy", {
                    "domain": args["domain"],
                    "object_list": args["object_list"],
                    "object_from": args["object_from"],
                })
    return h


def domain_policy_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "domain_policy_delete")
        with ctx.audit.trace("domain_policy_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/domain-policy", [str(args["id"])])
    return h


# =============================================================================
# QUARANTINE
# =============================================================================

def quarantine_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("quarantine_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/quarantine/all")
    return h


def quarantine_release(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("quarantine_release", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/qitem",
                    {"items": [str(i) for i in args["ids"]], "attr": {"action": "release"}},
                )
    return h


def quarantine_learn_spam(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("quarantine_learn_spam", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/qitem",
                    {"items": [str(i) for i in args["ids"]], "attr": {"action": "learnspam"}},
                )
    return h


def quarantine_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "quarantine_delete")
        with ctx.audit.trace("quarantine_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/qitem", [str(i) for i in args["ids"]])
    return h


def quarantine_set_notification(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("quarantine_set_notification", args):
            attr = {k: v for k, v in args.items() if k != "items"}
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/quarantine_notification",
                    {"items": ["all"], "attr": attr},
                )
    return h


# =============================================================================
# QUEUE
# =============================================================================

def queue_list(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("queue_list", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/mailq/all")
    return h


def queue_flush(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("queue_flush", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/mailq", {"items": ["flush"]})
    return h


def queue_delete(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        _require_confirm(args, "queue_delete")
        with ctx.audit.trace("queue_delete", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/delete/mailq", args["queue_ids"])
    return h


# =============================================================================
# FAIL2BAN
# =============================================================================

def fail2ban_get(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("fail2ban_get", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/fail2ban")
    return h


def fail2ban_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("fail2ban_update", args):
            attr: dict[str, Any] = {}
            for k_in, k_api in [
                ("ban_time", "ban_time"), ("max_attempts", "max_attempts"),
                ("retry_window", "retry_window"),
                ("whitelist", "whitelist"), ("blacklist", "blacklist"),
                ("manage_external", "manage_external"),
            ]:
                if k_in in args: attr[k_api] = args[k_in]
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/fail2ban", {"items": ["none"], "attr": attr})
    return h


def fail2ban_unban(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("fail2ban_unban", args):
            # unban via the edit endpoint with action=unban
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/fail2ban",
                    {"items": ["none"], "attr": {"action": "unban", "network": args["ip"]}},
                )
    return h


# =============================================================================
# RATELIMIT
# =============================================================================

def ratelimit_get_mailbox(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("ratelimit_get_mailbox", args):
            async with ctx.client() as c:
                return await c.get(f"/api/v1/get/rl-mbox/{args['email']}")
    return h


def ratelimit_set_mailbox(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("ratelimit_set_mailbox", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/rl-mbox/",
                    {
                        "items": [args["email"]],
                        "attr": {"rl_value": args["value"], "rl_frame": args["frame"]},
                    },
                )
    return h


def ratelimit_get_domain(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("ratelimit_get_domain", args):
            async with ctx.client() as c:
                return await c.get(f"/api/v1/get/rl-domain/{args['domain']}")
    return h


def ratelimit_set_domain(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("ratelimit_set_domain", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/rl-domain/",
                    {
                        "items": [args["domain"]],
                        "attr": {"rl_value": args["value"], "rl_frame": args["frame"]},
                    },
                )
    return h


# =============================================================================
# SPAM
# =============================================================================

def spam_score_get(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("spam_score_get", args):
            async with ctx.client() as c:
                target = args.get("email", "all")
                return await c.get(f"/api/v1/get/spam-score/{target}")
    return h


def spam_score_set(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("spam_score_set", args):
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/spam-score/",
                    {
                        "items": [args["email"]],
                        "attr": {
                            "spam_score": f"{args['low_score']},{args['high_score']}",
                        },
                    },
                )
    return h


# =============================================================================
# SETTINGS
# =============================================================================

def cors_settings_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("cors_settings_update", args):
            attr: dict[str, Any] = {}
            if "allowed_origins" in args: attr["allowed_origins"] = args["allowed_origins"]
            if "allowed_methods" in args: attr["allowed_methods"] = args["allowed_methods"]
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/cors", {"attr": attr})
    return h


def identity_provider_settings_update(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("identity_provider_settings_update", args):
            async with ctx.client() as c:
                return await c.post("/api/v1/edit/identity-provider", args)
    return h


def pushover_set(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("pushover_set", args):
            attr = {k: v for k, v in args.items() if k != "email"}
            attr["active"] = _b(attr.get("active", True))
            async with ctx.client() as c:
                return await c.post(
                    "/api/v1/edit/pushover",
                    {"items": [args["email"]], "attr": attr},
                )
    return h


# =============================================================================
# LOGS
# =============================================================================

def _logs_get_factory(name: str, mailcow_path: str) -> Callable[[AdminContext], ToolHandler]:
    def factory(ctx: AdminContext) -> ToolHandler:
        async def h(args: dict[str, Any]) -> Any:
            with ctx.audit.trace(name, args):
                lines = min(int(args.get("lines", 100)), 5000)
                async with ctx.client() as c:
                    return await c.get(f"/api/v1/get/logs/{mailcow_path}/{lines}")
        return h
    return factory


logs_get_postfix = _logs_get_factory("logs_get_postfix", "postfix")
logs_get_dovecot = _logs_get_factory("logs_get_dovecot", "dovecot")
logs_get_rspamd = _logs_get_factory("logs_get_rspamd", "rspamd-history")
logs_get_sogo = _logs_get_factory("logs_get_sogo", "sogo")
logs_get_acme = _logs_get_factory("logs_get_acme", "acme")
logs_get_netfilter = _logs_get_factory("logs_get_netfilter", "netfilter")
logs_get_watchdog = _logs_get_factory("logs_get_watchdog", "watchdog")
logs_get_api = _logs_get_factory("logs_get_api", "api")
logs_get_autodiscover = _logs_get_factory("logs_get_autodiscover", "autodiscover")
logs_get_ratelimit = _logs_get_factory("logs_get_ratelimit", "ratelimited")


# =============================================================================
# STATUS
# =============================================================================

def server_version(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("server_version", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/status/version")
    return h


def server_containers_status(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("server_containers_status", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/status/containers")
    return h


def server_vmail_status(ctx: AdminContext) -> ToolHandler:
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("server_vmail_status", args):
            async with ctx.client() as c:
                return await c.get("/api/v1/get/status/vmail")
    return h


def server_status_summary(ctx: AdminContext) -> ToolHandler:
    """Aggregated health snapshot — single tool call, multiple API endpoints.

    Returns counts and percentages for monitoring (Prometheus-friendly shape).
    """
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("server_status_summary", args):
            async with ctx.client() as c:
                version = await c.get("/api/v1/get/status/version")
                containers = await c.get("/api/v1/get/status/containers")
                vmail = await c.get("/api/v1/get/status/vmail")
                # Best-effort fetches: don't fail the whole summary if one
                # endpoint hiccups. Mailcow may return errors here under load.
                queue: Any = None
                fail2ban: Any = None
                try:
                    queue = await c.get("/api/v1/get/mailq/all")
                except Exception:
                    queue = None
                try:
                    fail2ban = await c.get("/api/v1/get/fail2ban")
                except Exception:
                    fail2ban = None

            cdict: dict[str, Any] = containers if isinstance(containers, dict) else {}
            running = sum(
                1 for v in cdict.values() if (v or {}).get("state") == "running"
            )
            # Mailcow's /status/containers does NOT expose Docker healthcheck
            # results — only state (running/exited/etc.). For per-container
            # health you'd need direct Docker access on the host. We surface
            # the count of containers reporting an explicit "healthy" status
            # if Mailcow ever adds it (forward-compat); otherwise None.
            healthy_vals = [
                (v or {}).get("status")
                for v in cdict.values()
                if (v or {}).get("state") == "running"
            ]
            if any(s for s in healthy_vals):
                healthy: int | None = sum(
                    1 for s in healthy_vals if s and "healthy" in str(s).lower()
                )
            else:
                healthy = None  # API doesn't report it
            down = sum(
                1 for v in cdict.values() if (v or {}).get("state") not in ("running", None)
            )

            # vmail disk percentage — Mailcow returns "used_percent": "13%" string
            vmail_pct: float | None = None
            if isinstance(vmail, dict):
                pct_str = str(vmail.get("used_percent", "")).rstrip("%")
                try:
                    vmail_pct = float(pct_str)
                except ValueError:
                    vmail_pct = None

            return {
                "version": version,
                "containers_total": len(cdict),
                "containers_running": running,
                "containers_healthy": healthy,
                "containers_down": down,
                "vmail": vmail,
                "vmail_disk_pct": vmail_pct,
                "queue_length": len(queue) if isinstance(queue, list) else None,
                "fail2ban_bans": (
                    len(fail2ban.get("active_bans") or [])
                    if isinstance(fail2ban, dict)
                    else None
                ),
            }
    return h


# =============================================================================
# DELIVERY
# =============================================================================

def send_test_mail(ctx: AdminContext) -> ToolHandler:
    """Send a test email by routing through the local Postfix container.

    Note: this tool requires Docker access on the Mailcow host (not just the
    REST API). When running the MCP elsewhere than the Mailcow host, this tool
    falls back to direct SMTP submission using the From address creds (which
    may not be available in admin mode). For now, it tries Docker first and
    raises NotImplementedError if not available.
    """
    async def h(args: dict[str, Any]) -> Any:
        with ctx.audit.trace("send_test_mail", args):
            import shutil
            import subprocess

            if not shutil.which("docker"):
                raise NotImplementedError(
                    "send_test_mail requires Docker access on the Mailcow host. "
                    "Run this tool from a machine with `docker exec` access to mailcowdockerized-postfix-mailcow-1, "
                    "or send via your own SMTP submission credentials."
                )
            msg = (
                f"Subject: {args.get('subject', 'Mailcow MCP delivery test')}\r\n"
                f"From: {args['from_addr']}\r\n"
                f"To: {args['to_addr']}\r\n\r\n"
                "Test message from mcp-mailcow.\r\n"
            )
            r = subprocess.run(
                ["docker", "exec", "-i", "mailcowdockerized-postfix-mailcow-1",
                 "sendmail", args["to_addr"]],
                input=msg.encode(), capture_output=True, timeout=30,
            )
            if r.returncode != 0:
                raise RuntimeError(f"sendmail failed: {r.stderr.decode()}")
            return {"status": "sent", "from": args["from_addr"], "to": args["to_addr"]}

    return h
