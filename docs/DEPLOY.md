# Guia de Deploy Gratuito (Supabase + Render)

Este guia explica como publicar o **Black Friday Tracker** na nuvem sem custos usando **Supabase** (autenticação + banco PostgreSQL por usuário) e **Render** (hospedagem Docker).

---

## 1. Configurar o Supabase (Banco + Login)

1. Acesse [supabase.com](https://supabase.com) e crie um projeto gratuito.
2. No menu esquerdo, abra **SQL Editor** → **+ New query**.
3. Cole todo o conteúdo de `supabase/schema.sql` e clique em **Run**.
   - Isso cria a tabela `public.tracker_data` e ativa o **Row Level Security (RLS)** para que cada usuário acesse apenas os próprios dados.
4. Vá em **Project Settings → API** (ou **API Keys**) e anote:
   - **Project URL** (`SUPABASE_URL`)
   - **Publishable / anon key** (`SUPABASE_ANON_KEY`) — **nunca** use a `Secret key` no app.

---

## 2. Subir o projeto para o GitHub

1. Crie um repositório no GitHub (público ou privado).
2. Confirme que o arquivo `.env` **não** será enviado (ele já está listado no `.gitignore`).
3. Envie os arquivos para o ramo `main` e, se quiser versionar a release:
   ```bash
   git init
   git add .
   git commit -m "chore: release v1.0.0"
   git tag -a v1.0.0 -m "Release v1.0.0"
   git branch -M main
   git remote add origin https://github.com/SEU_USUARIO/blackfriday-tracker.git
   git push -u origin main --tags
   ```

---

## 3. Publicar no Render (Plano Free)

1. Acesse [render.com](https://render.com) e clique em **New → Web Service**.
2. Conecte sua conta do GitHub e selecione o repositório `blackfriday-tracker`.
3. O Render detectará o `Dockerfile` e o `render.yaml` automaticamente:
   - **Runtime:** `Docker`
   - **Plan:** `Free`
4. Em **Environment Variables**, adicione:
   - `HOST` = `0.0.0.0`
   - `SUPABASE_URL` = sua Project URL do Supabase
   - `SUPABASE_ANON_KEY` = sua Publishable/anon key do Supabase
5. Clique em **Create Web Service** e aguarde o build finalizar.
6. O Render gerará uma URL pública no formato `https://blackfriday-tracker-xxxx.onrender.com`.

---

## 4. Ajustar URLs de Redirecionamento no Supabase

Para que o link de confirmação de e-mail redirecione para o site publicado (e não para `localhost:3000`):

1. No painel do Supabase, vá em **Authentication → URL Configuration**.
2. Em **Site URL**, coloque a URL do Render (`https://blackfriday-tracker-xxxx.onrender.com`).
3. Em **Redirect URLs**, adicione:
   - `https://blackfriday-tracker-xxxx.onrender.com/**`
   - `http://localhost:8080/**` (para testes locais)
4. Clique em **Save**.

> **Observação sobre o plano Free do Render:** após ~15 minutos sem acessos, o container entra em repouso e leva cerca de 30–50 segundos para responder na primeira requisição seguinte. Os dados dos usuários permanecem salvos normalmente no Supabase.
