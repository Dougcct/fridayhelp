# Black Friday Tracker

Painel para organizar produtos desejados, buscar ofertas automaticamente em lojas confiáveis, acompanhar histórico de preços e gerenciar metas de compra da Black Friday — com suporte a execução local (Docker/Python) e modo multiusuário na nuvem (**Supabase + Render**).

Versão atual: **`1.0.0`** (veja [CHANGELOG.md](CHANGELOG.md)).

## Funcionalidades

- **Grade de produtos (3 cards por linha)** com cores por categoria e filtro rápido em pills.
- **Busca automática de ofertas** (`POST /api/search`) na **KaBuM!** e no **Zoom**, com filtro de relevância por palavras-chave, correspondência numérica e contexto por categoria.
- **Paginação de ofertas** (até 3 ofertas por página em cada card) e exibição da marca do melhor item no painel de resumo.
- **Histórico de preços e linha do tempo** de atividades.
- **Persistência dupla**:
  - **Modo Local**: salva diretamente em `data/deals.json`.
  - **Modo Nuvem (Supabase)**: autenticação por e-mail/senha + banco PostgreSQL isolado por usuário via RLS.

## Estrutura do Projeto

- `index.html` — Interface web principal
- `css/style.css` — Estilos da aplicação (tema escuro responsivo)
- `js/app.js` — Lógica de interface, filtros, paginação, busca e autenticação
- `server.py` — Servidor HTTP em Python (stdlib, sem dependências externas) com API `/api/deals`, `/api/search` e `/api/auth/*`
- `data/deals.json` — Base de dados local em JSON
- `Dockerfile`, `compose.yaml`, `.dockerignore` — Configuração de container Docker
- `supabase/schema.sql` — Tabela `tracker_data` e políticas RLS por usuário
- `render.yaml` — Manifesto de deploy gratuito no Render
- `docs/DEPLOY.md` — Passo a passo completo para publicar no Supabase + Render
- `.env.example` — Modelo de variáveis de ambiente
- `VERSION` e `CHANGELOG.md` — Controle de versão

## Como Usar

### 1. Com Docker (Local)

1. Certifique-se de ter o Docker instalado e em execução.
2. *(Opcional)* Para testar conectado ao Supabase localmente, copie `.env.example` para `.env` e preencha `SUPABASE_URL` e `SUPABASE_ANON_KEY`.
3. Na pasta do projeto, execute:
   ```bash
   docker compose up -d --build
   ```
4. Acesse `http://localhost:8080`.
5. Para parar o container:
   ```bash
   docker compose down
   ```

### 2. Na Nuvem Gratuita (Supabase + Render)

Consulte o guia completo em [docs/DEPLOY.md](docs/DEPLOY.md).

### 3. Localmente com Python (sem Docker)

1. Execute `iniciar.bat` (Windows) ou `python server.py` no terminal dentro desta pasta.
2. Acesse `http://localhost:8080`.
