# Pre-checks en prod (2026-09-15) — Task 0

Todo lo ejecutado aquí es **read-only**: SQL solo `SELECT`, `docker exec` solo para leer o correr el script de calibración de τ (solo lee + 5 embeddings), `ss`/`docker inspect`/`dig`/`curl` de solo lectura. Sin `restart`, sin escritura, sin migraciones, sin cambios de config. `/tmp/tau-calibration.txt` se borró del host tras el `scp` (confirmado: `ls` post-borrado devuelve "No such file or directory").

Host: `root@89.167.115.45` (`pguerrero-prod`), acceso vía `ssh -o BatchMode=yes root@89.167.115.45 'bash -s' <<'EOF' ... EOF` (no interactivo, heredoc adaptado del brief).

## (b) longitud de full_text por fuente

```
    source     |  n   | max_chars |     p99_chars
---------------+------+-----------+-------------------
 webscraper    |   32 |    103713 | 78859.05999999998
 rss           | 2709 |     69398 | 6492.719999999994
 huggingface   | 2239 |      2053 |              1981
 arxiv         | 3985 |      1955 |              1949
 github        | 4421 |       669 |               341
 github_search | 1344 |       350 |            340.57
 hackernews    | 2507 |        86 |                80
(7 rows)
```

**Criterio**: informativo, no bloquea. `webscraper` tiene el `full_text` más largo con diferencia (max 103.713 chars, p99 ~78.8k chars) — muy por encima de arxiv/rss/hn. Claude Code guarda a fichero las respuestas de tool_result >25k tokens (~100k chars aprox.), así que un `full_text` de webscraper cerca del máximo podría acercarse a ese umbral si se devuelve completo sin truncar; no bloquea el diseño, pero es dato a tener presente si `find_similar`/`search_news` devuelven `full_text` sin recortar.

## (c) cobertura de embeddings y metadata

**(c1) cobertura de embeddings del modelo activo (`text-embedding-3-small`)**

```
    source     | total | with_embedding
---------------+-------+----------------
 arxiv         |  3985 |           3985
 github        |  4421 |           4421
 github_search |  1344 |           1344
 hackernews    |  2507 |           2507
 huggingface   |  2239 |           2239
 rss           |  2709 |           2709
 webscraper    |    32 |             32
(7 rows)
```

Cobertura 100% en las 7 fuentes (`total == with_embedding` en todas). Informativo — se documenta en la descripción de `find_similar`: no hay huecos de embedding que dejen candidatos sin vector para el modelo activo.

**(c2) metadata.type en Hugging Face**

```
    type     | count
-------------+-------
 model       |   415
 daily_paper |  1824
(2 rows)
```

415 + 1824 = 2239 = total de filas `huggingface` de la query (c1). **No hay filas con `type` NULL** — no aplica la anotación de "decisión 9" (`engagement: null`) porque no hay HF items sin tipo clasificado a fecha de hoy.

**(extra) versión de pgvector**

```
 extversion
------------
 0.8.2
(1 row)
```

Informativo (el diseño no depende de ella).

## (d) Traefik y proxy delante

```
== ss -tlnp :443 ==
State  Recv-Q Send-Q Local Address:Port Peer Address:Port Process
LISTEN 0      4096         0.0.0.0:443       0.0.0.0:*    users:(("docker-proxy",pid=2629668,fd=4))
LISTEN 0      4096            [::]:443          [::]:*    users:(("docker-proxy",pid=2629673,fd=4))

== docker ps proxy/traefik ==
coolify-proxy traefik:v3.6

== coolify-proxy Cmd (completo) ==
["--ping=true","--ping.entrypoint=http","--api.dashboard=true",
 "--entrypoints.http.address=:80","--entrypoints.https.address=:443",
 "--entrypoints.http.http.encodequerysemicolons=true","--entryPoints.http.http2.maxConcurrentStreams=250",
 "--entrypoints.https.http.encodequerysemicolons=true","--entryPoints.https.http2.maxConcurrentStreams=250",
 "--entrypoints.https.http3","--providers.file.directory=/traefik/dynamic/","--providers.file.watch=true",
 "--certificatesresolvers.letsencrypt.acme.httpchallenge=true",
 "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=http",
 "--certificatesresolvers.letsencrypt.acme.storage=/traefik/acme.json",
 "--api.insecure=false","--providers.docker=true","--providers.docker.exposedbydefault=false"]
```

`grep -i forwarded` sobre el Cmd no devolvió nada: `forwardedHeaders` no está en los flags de arranque (`Cmd`); si existe, vive en el provider de fichero (`--providers.file.directory=/traefik/dynamic/`), no inspeccionado aquí (fuera de alcance read-only mínimo de este pre-check). Informativo — va a la enmienda de ADR-001, no bloquea.

```
== dig +short pguerrero.me ==
89.167.115.45

== curl -sI https://pguerrero.me/ai-news/ | grep -iE '^(server|cf-ray|via|x-cache)' ==
server: nginx/1.27.5
```

**Evaluación del criterio STOP**: puerto 443 lo escucha únicamente `docker-proxy` (el único proceso listado; ese es el proxy Docker userland delante del contenedor `coolify-proxy`/Traefik, comportamiento esperado de Docker, no un proxy adicional). `docker ps | grep -iE 'proxy|traefik'` solo devuelve `coolify-proxy` (imagen `traefik:v3.6`) — ningún nginx/caddy/haproxy standalone corriendo en el host. `dig` resuelve directo a la IP del VPS (sin CDN/Cloudflare delante). El header `server: nginx/1.27.5` es el nginx interno del stack de la app (documentado en el proyecto: `api + frontend + postgres + nginx`), no un proxy externo — no aparecen `cf-ray` ni `via`.

**Resultado: NO STOP.** No hay proxy distinto de Traefik delante; `RemoteAddr` que ve Traefik es el cliente real (o, como mucho, `docker-proxy` que preserva la IP origen — no añade otro hop de red pública). Quitar `depth=1` sí daría buckets por cliente real.

## (e) sesgo de recencia (decisión 1, ya resuelto por código)

`frontend/src/pages/Discover.tsx:138` usa `/api/search/semantic` → la web conserva el sesgo de recencia (`recent_first=true` por defecto); el MCP pasa `recent_first=false`.
