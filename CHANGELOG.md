# Changelog

Todas as mudanças relevantes do **Friday Help** são documentadas neste arquivo.

O versionamento segue o padrão [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.0.0] - 2026-11-22

### Adicionado
- **Containerização Docker**: `Dockerfile`, `compose.yaml` e `.dockerignore` com `HEALTHCHECK` e encerramento gracioso (`SIGTERM`).
- **Busca automática em lojas nacionais (`POST /api/search`)**: consulta paralela em **KaBuM!**, **Carrefour**, **Kalunga**, **Dafiti** e **Zoom (Comparador)**, com separação de termos colados (`ssd240gb`), bloqueio de sistemas inteiros na busca de peças, exclusão de acessórios e filtro de preços fora da curva.
- **Interface Friday Help (PC e celular)**:
  - Ícone principal SVG + favicon e ícones nos botões, abas e KPIs.
  - Grade de 3 cards por linha no desktop e layout responsivo para celular.
  - Cores distintas por categoria (incluindo **Moda & Beleza**, **Som Automotivo**, **Esporte & Lazer**, **Hardware**) e filtro rápido em pills.
  - Paginação de ofertas por card (até 3 por página), extração da marca do melhor item e barra de ações compacta com ícones.
