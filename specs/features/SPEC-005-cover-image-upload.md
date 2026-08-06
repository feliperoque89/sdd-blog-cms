# SPEC-005 — Upload de Imagem de Capa

## Status
Implementado

## Objetivo
Permitir que Editor/Admin enviem um arquivo de imagem (em vez de colar uma
URL externa) para usar como capa (`cover_image_url`) de um post, armazenado
no MinIO (S3-compatible), conforme já previsto em `specs/PRODUCT.md`
("Upload de imagem de capa (armazenada via MinIO)") e
`specs/ARCHITECTURE.md` (componente `minio` — "Storage de mídia").

## Contexto
SPEC-002 já define `cover_image_url` como campo opcional do post, mas hoje é
só um campo de texto livre no `PostEditor` — o editor precisa hospedar a
imagem em outro lugar e colar a URL manualmente. `minio` já está provisionado
em `k8s/05-minio.yaml`, mas nenhum código do backend fala com ele ainda; esta
spec adiciona essa integração e o componente de upload no frontend, que
substitui o campo de texto.

Depende de SPEC-001 (autenticação) para a rota administrativa.

## Requisitos funcionais

- RF01: `POST /api/admin/media/cover-image` (`multipart/form-data`, campo
  `file`) envia um arquivo de imagem para o MinIO e retorna sua URL pública.
- RF02: Tipos aceitos: `image/jpeg`, `image/png`, `image/webp` — validados
  pelo `Content-Type` declarado **e** pela assinatura real do arquivo (magic
  bytes), não apenas pela extensão/header informado pelo cliente.
- RF03: Tamanho máximo: 5MB. Arquivos maiores são rejeitados antes de serem
  gravados no MinIO.
- RF04: O nome do objeto no bucket é gerado pelo backend (UUID + extensão
  inferida do tipo real do arquivo) — o nome original do arquivo enviado
  pelo cliente nunca é usado como chave de armazenamento.
- RF05: `PostEditor` (frontend) substitui o campo de texto livre de
  `cover_image_url` por um componente de upload: seleciona um arquivo, mostra
  progresso, e ao concluir preenche `cover_image_url` automaticamente com a
  URL retornada. Se o post (modo edição) já tiver uma capa, mostra um preview
  da imagem atual antes de qualquer novo upload.

## Requisitos não funcionais

- RNF01: Rota exige autenticação `editor`|`admin` (mesmo padrão de
  `posts_admin.py`).
- RNF02: Bucket do MinIO com política de leitura pública somente para o
  bucket de mídia (least privilege — nenhum outro bucket/recurso do MinIO é
  exposto publicamente).
- RNF03: Falha de comunicação com o MinIO (indisponível, credenciais
  inválidas, etc.) retorna um erro genérico ao cliente (nunca o detalhe
  interno) — mesmo espírito de RNF02 da SPEC-003 para a API da LLM. Detalhe
  real vai só para o log do servidor.
- RNF04: Client de storage (`app/services/media_storage_service.py` ou
  similar) é uma interface substituível por dependency override em testes —
  nenhum teste unitário fala com um MinIO/S3 real (`specs/TESTING.md`).

## Contrato de API

### `POST /api/admin/media/cover-image` (auth: editor|admin)
Request: `multipart/form-data` com campo `file` (imagem).

Response `201`:
```json
{ "url": "string" }
```

Erros:
- `422`: `file` ausente, tipo não permitido (declarado ou detectado por
  assinatura), ou tamanho acima de 5MB.
- `401`: sem autenticação.
- `502`: falha ao gravar no MinIO (mensagem genérica).

## Critérios de aceite

1. **Dado** um arquivo JPEG de 2MB, **quando** enviado via
   `POST /api/admin/media/cover-image`, **então** retorna `201` com uma URL
   pública apontando para o arquivo armazenado no MinIO.
2. **Dado** um arquivo `.pdf` renomeado para `capa.jpg` (Content-Type
   `image/jpeg` declarado, mas assinatura real não é de imagem), **quando**
   enviado, **então** retorna `422` e nada é gravado no MinIO.
3. **Dado** um arquivo JPEG de 8MB, **quando** enviado, **então** retorna
   `422` e nada é gravado no MinIO.
4. **Dado** um usuário sem autenticação, **quando** tenta enviar um arquivo,
   **então** recebe `401`.
5. **Dado** um upload bem-sucedido no `PostEditor`, **quando** o post é
   salvo, **então** `cover_image_url` enviado em `POST`/`PUT /api/admin/posts`
   é exatamente a URL retornada pelo upload.
6. **Dado** um post em modo edição já com `cover_image_url` preenchido,
   **quando** a tela abre, **então** o componente mostra um preview da
   imagem atual antes de qualquer novo upload.
7. **Dado** uma falha ao gravar no MinIO (simulada via mock em teste),
   **quando** o upload é tentado, **então** a API retorna `502` com mensagem
   genérica e o `PostEditor` mostra essa mensagem via `role="alert"`, sem
   quebrar o restante do formulário.

## Casos de teste obrigatórios

- Upload bem-sucedido para cada tipo permitido (`jpeg`/`png`/`webp`) — `201`
  com `url`.
- Tipo de arquivo não permitido (declarado ou detectado por assinatura) —
  `422`, sem chamar o client de storage.
- Arquivo acima do limite de tamanho — `422`, sem chamar o client de
  storage.
- Nome do objeto gravado no bucket nunca é o nome original do arquivo
  enviado (RF04).
- `401` sem autenticação.
- Falha do client de storage (mock levantando exceção) — `502`, mensagem
  genérica, nenhum detalhe interno na resposta.
- Frontend: seleciona um arquivo, mostra estado de carregamento, chama
  `POST /api/admin/media/cover-image`, preenche `cover_image_url` com a URL
  retornada ao concluir.
- Frontend: post em edição com `cover_image_url` existente mostra preview
  ao montar.
- Frontend: erro da API durante upload aparece via `role="alert"`, sem
  travar o restante do formulário nem impedir nova tentativa.

## Fora de escopo
- Redimensionamento/otimização/geração de thumbnails da imagem — considerar
  em spec futura.
- Múltiplas imagens por post (galeria) — só a capa.
- Exclusão do arquivo antigo no MinIO ao substituir a capa por um novo
  upload (o objeto anterior fica órfão no bucket) — aceitável para v1.
- Upload direto do frontend para o MinIO via URL pré-assinada (presigned
  URL) — v1 faz o upload sempre através do backend, que valida antes de
  gravar.
- Editor colar uma URL externa manualmente — RF05 remove essa opção; se for
  necessário no futuro, tratar em spec própria.
