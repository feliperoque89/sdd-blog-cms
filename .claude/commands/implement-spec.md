Você vai implementar a spec indicada seguindo TDD e as convenções descritas
em `CLAUDE.md` e `specs/TESTING.md`.

Spec a implementar: $ARGUMENTS

Passos obrigatórios:

1. Leia a spec completa em `specs/features/`. Se o arquivo não existir, pare
   e avise — não invente a spec, use `/new-spec` primeiro.
2. Leia `CLAUDE.md`, `specs/ARCHITECTURE.md` e `specs/TESTING.md` para
   confirmar convenções de pastas, nomenclatura e stack antes de escrever
   qualquer arquivo.
3. Liste, em texto, todos os critérios de aceite e casos de teste
   obrigatórios da spec antes de começar a codar. Isso vira seu checklist.
4. Para cada critério de aceite:
   a. Escreva primeiro o teste unitário (backend: pytest em
      `backend/tests/unit/`; frontend: Vitest em `frontend/tests/unit/`),
      nomeado com o sufixo da spec (ex: `_spec003`). Rode e confirme que
      falha (red).
   b. Implemente o código mínimo necessário para o teste passar (green).
   c. Refatore se necessário, mantendo os testes passando.
5. Toda chamada a serviço externo (LLM, storage, e-mail) deve ser mockada
   nos testes unitários — nunca chame a API real durante os testes. Se a
   spec envolver a IA generativa, crie fixtures de resposta de sucesso, erro
   e timeout conforme `specs/TESTING.md`.
6. Depois de cobrir todos os critérios de aceite com testes unitários
   passando, rode a suíte completa (`pytest --cov` e/ou `npm run test`) e
   confirme que a cobertura da feature está ≥ 80%.
7. Atualize o `## Status` da spec de `Rascunho` para `Implementado` somente
   depois que todos os testes passarem.
8. Ao final, mostre um resumo: arquivos criados/alterados, comandos para
   rodar os testes localmente, e qualquer critério de aceite que não pôde
   ser coberto (com justificativa).

Não pule etapas de teste para "ir mais rápido". Se algo na spec estiver
subespecificado para implementar com segurança, pare e pergunte em vez de
assumir.

## Delegação a subagentes

Sempre que a spec envolver tanto backend quanto frontend, delegue em vez de
implementar tudo você mesmo na conversa principal:

- Use o subagente `test-writer` para escrever os testes derivados dos
  critérios de aceite antes de qualquer implementação.
- Use o subagente `backend-builder` para a parte de `backend/`.
- Use o subagente `frontend-builder` para a parte de `frontend/`.
- Se a spec envolver qualquer chamada à LLM (ex: SPEC-003 ou futuras
  features de IA), rode o subagente `ai-safety-reviewer` ao final,
  obrigatoriamente, antes de marcar a spec como `Implementado`.

Isso mantém a conversa principal limpa e cada subagente focado em seu
próprio escopo de arquivos.
