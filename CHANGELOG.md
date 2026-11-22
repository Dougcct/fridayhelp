# Changelog

Todas as mudanças relevantes do **Black Friday Tracker** são documentadas neste arquivo.

O versionamento segue o padrão [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-11-22

### Adicionado
- **Containerização Docker**: `Dockerfile`, `compose.yaml` e `.dockerignore` com `HEALTHCHECK` e encerramento gracioso (`SIGTERM`).
- **Busca automática de ofertas (`POST /api/search`)**: consulta paralela na **KaBuM!** e no **Zoom**, com priorização de anúncios diretos em estoque na KaBuM!, filtro por relevância, correspondência numérica exata e dicas/exclusões por categoria (`CATEGORY_HINTS`).
- **Interface em grade (3 cards por linha)**:
  - Cores distintas por categoria e barra de filtro rápido em pills (`#categoryPills`).
  - Categorias expandidas, incluindo **Moda & Beleza**, **Som Automotivo**, **Esporte & Lazer**, **Hardware**, entre outras.
  - Paginação de ofertas por card (máximo de 3 ofertas por página).
  - Exibição da marca do melhor item em destaque no painel de resumo e barra compacta de ações com ícones (Lupa, Lápis, X).
- **Modo Nuvem Gratuita (Supabase + Render)**:
  - Endpoints `/api/auth/status`, `/api/auth/login`, `/api/auth/signup` e `/api/auth/logout` com cookie `HttpOnly`.
  - Schema SQL com isolamento por usuário via Row Level Security (`supabase/schema.sql`).
  - Manifesto `render.yaml` e guia `docs/DEPLOY.md` para deploy gratuito no Render.
