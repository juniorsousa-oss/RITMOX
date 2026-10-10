# Migração do RITMOX para Hostinger — checklist seguro

## Estado atual

- Produção legada: Render, FastAPI, banco PostgreSQL no esquema `ritmox`.
- **Não mover, excluir ou recriar** as tabelas antigas.
- Banco compartilhado no Supabase: não alterar os esquemas de outros apps.
- Branch de homologação: `feat/hostinger-multiuser` (PR #3).
- Novos usuários: cada um terá seu próprio esquema `ritmox_u_<id>`.
- Autenticação central: esquema `ritmox_auth`, com senhas PBKDF2-SHA256
  e tokens de sessão armazenados somente como hashes.
- **A primeira conta administradora mantém o esquema legado `ritmox`**,
  inclusive treinos, perfil, planos e histórico já existentes.

## Administração principal

A primeira conta criada com `RITMOX_ADMIN_EMAIL` e
`RITMOX_ADMIN_PASSWORD` será o **administrador principal** e continuará
vinculada ao esquema legado `ritmox`. Apenas essa conta, nesta primeira
versão, poderá:

- criar e desativar usuários;
- ligar ou desligar módulos globalmente;
- controlar as permissões individuais de acesso aos módulos;
- definir as cores, a logo e o favicon que aparecem em todos os usuários.

Os módulos Início e Perfil são essenciais e não podem ser bloqueados.
A assinatura **by Nexon Labs** é permanente e não pode ser substituída
nem ocultada pelo painel de personalização. Todos os controles são
verificados nos endpoints do backend, não apenas no menu.

Para configurar, entrar como admin e abrir `/conta`.

## Regras de publicação

1. Criar backup recuperável do esquema `ritmox` antes de iniciar
   a nova versão com acesso ao banco real. Confirmar restauração de amostra.
2. Validar todo o PR #3 (CI SQLite, PostgreSQL e build Docker).
3. Definir conta administradora (e-mail e nome). A senha inicial deve
   ser definida **diretamente no terminal da VPS**, nunca no chat nem no GitHub.
4. Preparar `/docker/ritmox/.env` com permissões restritas (0600).
   Configurar conexão do Supabase/PostgreSQL, admin e cookies HTTPS.
5. Preparar acesso TLS/Traefik para `ritmox.nexonlabs.com.br`, evitando
   indisponibilidade dos serviços atuais.
6. Aprovar merge para `main` **somente na janela de publicação**.
   Render pode estar com autodeploy ligado.
7. Fazer o deploy de `ritmox` em container dedicado na mesma VPS:
   `cd /docker/ritmox && docker compose build --no-cache --pull ritmox`;
   depois `docker compose up -d --force-recreate ritmox`.
8. Confirmar `docker compose ps` saudável, `/health` sem erros,
   login, recuperação do perfil e dos treinos existentes.
9. Cadastrar um segundo usuário de teste pelo painel `/conta`;
   confirmar que seu histórico começa vazio e que ele **não vê** dados
   do primeiro usuário. Validar criação e execução de um treino de teste.
10. Após validação no domínio e aceite, desligar o Render para
    não manter uma instância antiga sem proteção.

## Variáveis no Hostinger (segredos NÃO devem ser versionados)

- `DATABASE_URL`: conexão PostgreSQL já usada pelo RITMOX.
- `DB_SCHEMA=ritmox`.
- `REQUIRE_PERSISTENT_DB=true`.
- `RITMOX_REQUIRE_AUTH=true`.
- `RITMOX_COOKIE_SECURE=true`.
- `RITMOX_ADMIN_EMAIL`, `RITMOX_ADMIN_NAME`, `RITMOX_ADMIN_PASSWORD`.
- `PROFESSIONAL_APPROVAL_KEY` se houver profissional responsável.
- `STRAVA_CLIENT_ID` e `STRAVA_CLIENT_SECRET` apenas quando integrados.

## Isolamento e segurança

Cada login usa um mecanismo de sessão HttpOnly, SameSite=Strict,
HTTPS e validação CSRF. A autorização ocorre antes dos endpoints `/api/`
(com exceção da autenticação inicial e do diagnóstico público).
O mecanismo de dados determina um `search_path` fixo por conta usando
**um pool de conexões dedicado**. Isso impede que consultas antigas da
aplicação, feitas sem `WHERE user_id`, acessem o esquema de outro usuário.
A conta administradora não acessa automaticamente o histórico privado
dos demais usuários.

A criação de um novo usuário configura todas as tabelas e perguntas
iniciais de anamnese em seu esquema isolado. Isso é uma solução de
isolamento rigoroso para a migração da aplicação atual, construída para
um usuário, preservando integralmente as consultas e registros legados.

## Rollback

Até o corte, Render e o esquema `ritmox` permanecem intocados.
Se a imagem nova falhar, manter o Render em operação, sem alternar os
esquemas antigos, corrigir na branch e reconstruir a nova imagem.
Não apagar `ritmox_auth` nem os esquemas `ritmox_u_<id>` sem backup
e análise explícita dos dados.
