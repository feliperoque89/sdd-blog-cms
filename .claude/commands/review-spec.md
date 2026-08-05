Você vai auditar se a implementação atual do código cumpre integralmente a
spec indicada — sem alterar código, apenas gerando um relatório.

Spec a revisar: $ARGUMENTS

Passos obrigatórios:

1. Leia a spec completa em `specs/features/`.
2. Localize o código relacionado (routers, services, schemas, componentes
   de frontend) e os testes relacionados.
3. Para cada requisito funcional e não funcional da spec, responda:
   - Está implementado? (sim/não/parcial)
   - Está coberto por teste automatizado? (sim/não)
   - Se não estiver, qual o gap específico?
4. Para cada critério de aceite (Dado/Quando/Então), aponte qual teste (se
   houver) o valida. Se nenhum teste validar, sinalize como gap.
5. Verifique especificamente os itens de segurança/robustez da spec, se
   houver (ex: rate limiting, sanitização de input, tratamento de erro de
   dependência externa, autorização por papel) — esses costumam ser
   esquecidos.
6. Verifique se o `## Status` da spec reflete a realidade (ex: marcada como
   `Implementado` mas com gaps encontrados).
7. Produza um relatório final em markdown com:
   - Resumo (% de critérios atendidos).
   - Tabela de requisitos x status x cobertura de teste.
   - Lista de gaps priorizados (crítico / médio / baixo).
   - Sugestão de próximos passos (ex: rodar `/implement-spec` de novo para
     fechar os gaps, ou `/write-tests` se o código existe mas falta teste).

Não corrija nada automaticamente neste comando — apenas relate.

## Delegação a subagentes

Delegue a auditoria em si ao subagente `spec-reviewer` (ele já segue este
mesmo roteiro e produz o relatório no formato padrão). Se a spec revisada
envolver chamadas à LLM, rode também o subagente `ai-safety-reviewer` e
inclua os achados dele na mesma resposta.
