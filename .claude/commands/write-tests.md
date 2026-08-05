Você vai gerar ou completar testes unitários faltantes para o código/spec
indicado, seguindo `specs/TESTING.md`.

Alvo: $ARGUMENTS

Passos obrigatórios:

1. Identifique a spec correspondente em `specs/features/` (pelo nome do
   arquivo/módulo de código ou pelo argumento passado). Se não achar
   nenhuma spec relacionada, avise antes de continuar — testes sem spec
   associada quebram a rastreabilidade do projeto.
2. Compare os critérios de aceite e casos de teste obrigatórios da spec com
   os testes já existentes no diretório correspondente
   (`backend/tests/unit/` ou `frontend/tests/unit/`).
3. Liste explicitamente quais critérios ainda não têm teste.
4. Escreva os testes faltantes:
   - Backend: pytest, mockando qualquer dependência externa (LLM, banco real,
     storage). Use fixtures existentes em `backend/tests/` quando possível;
     crie novas apenas se necessário.
   - Frontend: Vitest + React Testing Library, mockando chamadas de API via
     MSW.
5. Nomeie os testes referenciando a spec (`_specXXX` no nome da função ou
   describe block).
6. Rode a suíte e confirme que os novos testes passam e que nenhum teste
   existente quebrou.
7. Reporte a cobertura antes/depois (se a ferramenta de cobertura estiver
   configurada).

Não modifique o código de produção neste comando a menos que o teste revele
um bug real — nesse caso, pare, explique o bug encontrado e pergunte antes
de corrigir.

## Delegação a subagentes

Delegue a escrita dos testes ao subagente `test-writer`, que já segue as
regras de mocking e nomenclatura de `specs/TESTING.md`.
