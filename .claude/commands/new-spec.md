Você vai criar uma nova spec de feature para este projeto, seguindo
rigorosamente a metodologia SDD descrita em `CLAUDE.md`.

Feature solicitada: $ARGUMENTS

Passos obrigatórios:

1. Leia `CLAUDE.md`, `specs/PRODUCT.md` e `specs/ARCHITECTURE.md` para
   entender o contexto do projeto antes de escrever qualquer coisa.
2. Verifique em `specs/features/` se já existe uma spec relacionada. Se
   existir, avise e pergunte se devo editar a existente em vez de criar uma
   nova.
3. Descubra o próximo número disponível (`SPEC-XXX`) olhando os arquivos já
   existentes em `specs/features/`.
4. Se a descrição da feature for ambígua ou faltar informação crítica
   (ex: regras de negócio, quem pode acessar, limites), faça no máximo 2-3
   perguntas objetivas antes de escrever a spec. Não invente requisitos de
   negócio importantes sem confirmar.
5. Crie o arquivo `specs/features/SPEC-XXX-slug-da-feature.md` usando
   exatamente esta estrutura (siga o padrão de SPEC-001/002/003 já
   existentes):

```
# SPEC-XXX — <Título>

## Status
Rascunho

## Objetivo
## Contexto
## Requisitos funcionais
## Requisitos não funcionais
## Contrato de API
## Critérios de aceite
## Casos de teste obrigatórios
## Fora de escopo
```

6. Critérios de aceite devem estar no formato Dado/Quando/Então, e devem ser
   diretamente traduzíveis em testes automatizados.
7. Casos de teste obrigatórios devem cobrir: caminho feliz, erros de
   validação, autorização, e falhas de dependências externas (se aplicável).
8. Não implemente código nesta etapa. Apenas a spec. Ao final, mostre um
   resumo do que foi criado e pergunte se está aprovada antes de eu rodar
   `/implement-spec`.
