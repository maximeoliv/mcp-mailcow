# Pattern : exposer l'API Mailcow au tailnet via Tailscale Serve

Si ton Mailcow utilise un filtre IP (`API_ALLOW_FROM` dans `mailcow.conf`)
pour restreindre l'accès à l'API REST, et que tu veux que le MCP
fonctionne depuis une autre machine de ton tailnet sans whitelister
chaque IP publique sortante, tu peux **proxifier l'API via Tailscale
Serve**.

## Setup côté Mailcow host

```bash
# Sur la machine qui héberge Mailcow (root)
tailscale serve --bg --https=8443 https+insecure://localhost:443
```

Ce qui se passe :
- Tailscale Serve écoute sur `https://<hostname>.<tailnet>.ts.net:8443`
  avec un cert Let's Encrypt valide (auto-géré par Tailscale).
- Les requêtes sont reverse-proxifiées vers `https://localhost:443` côté
  backend (Mailcow nginx). Le `+insecure` skip la vérif TLS sur le backend
  (cert public du Mailcow ne match pas `localhost`).

## ⚠ Attention : Mailcow voit l'IP tailnet du peer, pas `127.0.0.1`

Tailscale Serve transmet l'IP du peer (l'IP tailnet de la machine
cliente) via le header `X-Forwarded-For`. Mailcow nginx est configuré
avec `real_ip_header X-Forwarded-For` + `set_real_ip_from` permissif sur
les CIDR privés. Du coup PHP côté API Mailcow lit l'IP **tailnet** du
peer comme IP source — pas `127.0.0.1`.

**Conséquence pratique** : il faut whitelister l'IP **tailnet** du peer
(pas localhost) dans `API_ALLOW_FROM`.

```ini
# /opt/mailcow-dockerized/mailcow.conf
API_ALLOW_FROM=127.0.0.1,172.22.1.1,155.117.100.28,100.X.Y.Z
#                                                  ^^^^^^^^^
#                              IP tailnet de ta machine cliente MCP
```

Ensuite recreate les conteneurs `php-fpm` et `nginx` Mailcow pour
charger la nouvelle valeur :

```bash
cd /opt/mailcow-dockerized
docker compose down php-fpm-mailcow nginx-mailcow
docker compose up -d php-fpm-mailcow nginx-mailcow
```

## Setup côté client MCP

```json
{
  "mcpServers": {
    "mailcow-admin": {
      "command": "uvx",
      "args": ["mcp-mailcow", "--mode", "admin"],
      "env": {
        "MAILCOW_ADMIN_URL": "https://your-mailcow.tail-XXXX.ts.net:8443",
        "MAILCOW_ADMIN_API_KEY": "...",
        "MCP_MAILCOW_TLS_VERIFY": "true"
      }
    }
  }
}
```

## Avantages

- **Pas d'exposition publique** : le port 8443 est tailnet-only.
- **IP tailnet stable** : contrairement aux IPs publiques sortantes
  (notamment celles du cloud Shadow.tech qui changent à chaque session),
  l'IP tailnet d'un peer reste fixe tant que la machine est dans le
  tailnet. Une seule entrée dans `API_ALLOW_FROM` suffit.
- **TLS bout-en-bout** : cert ts.net valide côté client, cert public
  Mailcow côté backend (re-encrypté en interne).

## Inconvénients / pièges

- **Diagnostic moins évident** quand ça foire : il faut connaître le
  pattern X-Forwarded-For. Symptôme classique : 401 avec `api access
  denied for ip 100.X.Y.Z` (pas `127.0.0.1` comme on s'y attendrait).
- **Durabilité du `tailscale serve`** : la conf survit aux reboots
  (stockée dans tailscaled state) mais pas à un changement majeur de
  Tailscale. Vérifier `tailscale serve status` en cas de doute.

## Alternative : pas de filtre IP du tout

Si la sécu API key + Tailscale ACL te suffit, tu peux désactiver
`API_ALLOW_FROM` dans `mailcow.conf` (le commenter) → l'API accepte
toutes les sources IP, seule la clé fait foi. Plus simple mais une
couche de défense en moins.
