# Friday Help

Painel local para organizar produtos desejados, buscar ofertas automaticamente em lojas nacionais confiáveis, acompanhar histórico de preços e gerenciar metas de compra da Black Friday — rodando em container Docker ou Python local.

Versão atual: **`1.0.0`** (veja [CHANGELOG.md](CHANGELOG.md)).

## Funcionalidades

- **Grade de produtos (3 cards por linha no PC, responsivo no celular)** com cores por categoria e filtro rápido em pills.
- **Busca automática de ofertas (`POST /api/search`)** em lojas nacionais (**KaBuM!**, **Carrefour**, **Kalunga**, **Dafiti** e **Zoom Comparador**), com normalização de termos (`ssd240gb` → `ssd 240gb`), bloqueio de PCs inteiros na busca de peças, filtro de acessórios e filtro anti-outlier de preço.
- **Paginação de ofertas** (até 3 ofertas por página em cada card) e exibição da marca do melhor item no painel de resumo.
- **Persistência local automática** em `data/deals.json` via volume Docker (`./data:/app/data`).

## Estrutura do Projeto

- `index.html` — Interface web principal
- `css/style.css` — Estilos da aplicação (tema escuro responsivo para PC e celular)
- `js/app.js` — Lógica de interface, filtros, paginação e busca automática
- `server.py` — Servidor HTTP em Python (stdlib, sem dependências externas) com `/api/deals` e `/api/search`
- `data/deals.json` — Base de dados local em JSON
- `Dockerfile`, `compose.yaml`, `.dockerignore` — Configuração de container Docker
- `iniciar.bat` — Atalho para iniciar localmente com Python no Windows
- `VERSION` e `CHANGELOG.md` — Controle de versão

## Como Usar

### Com Docker (recomendado)

1. Certifique-se de ter o Docker instalado e em execução.
2. Na pasta do projeto, execute:
   ```bash
   docker compose up -d --build
   ```
3. Acesse `http://localhost:8080`.
4. Para parar o container:
   ```bash
   docker compose down
   ```

### Localmente com Python (sem Docker)

1. Execute `iniciar.bat` (Windows) ou `python server.py` no terminal dentro desta pasta.
2. Acesse `http://localhost:8080`.
