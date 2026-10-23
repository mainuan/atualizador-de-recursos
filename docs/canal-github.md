# Publicação pelo canal GitHub — versão 0.2.2

Não existe configuração inicial de chaves, GitHub Apps ou APT próprio. O aplicativo
instalado funciona com `mainuan-atualizador-recursos`, como usuário comum. Não use
sudo: a autorização administrativa pertence ao agente PolicyKit.

## Rotina de publicação

1. Desenvolva e teste o programa no Mainuan baseado no Kubuntu 26.04.
2. Publique uma release pública **estável**, sem draft/prerelease, na organização
   **mainuan**, anexando `pacote_versão_arquitetura.deb`. O nome real do pacote pode
   diferir do repositório. A arquitetura deve ser `all` ou a arquitetura Debian do
   computador, por exemplo `amd64`. Os campos internos Package, Version e
   Architecture precisam corresponder ao nome do arquivo. As dependências devem
   estar disponíveis e satisfeitas no Mainuan.
3. Confirme o campo `digest: sha256:...` do asset na API do GitHub. Esse checksum
   é gerado e publicado pelo GitHub, não uma assinatura do desenvolvedor. Sem ele,
   o pacote é bloqueado. Anexar SHA256SUMS também permite a verificação humana,
   mas o aplicativo exige e compara o digest da API.
4. Edite `packages.txt` na main de `mainuan/atualizadorderecursos`: um nome de
   repositório por linha, sem URL, versão ou comando. Linhas vazias e comentários
   iniciados por `#` são aceitos. Repetições são rejeitadas.
5. Edite `message.txt`: mensagem livre em português, preservando parágrafos e
   quebras de linha. A lista de programas usa automaticamente nomes das releases.
6. Salve no GitHub. Prefira salvar ambos os arquivos no mesmo commit se precisarem
   mudar juntos. Não há assinatura, JSON nem workflow de catálogo para executar.

Exemplo atual, com repositório real, de `packages.txt`:

```text
mainuan-gestao-drivers
```

Exemplo de `message.txt`:

```text
Olá! O Mainuan tem novidades.

Confira quais são:
```

Outros programas seguem o mesmo formato depois de publicados oficialmente. O
aplicativo procura a release estável mais recente **com Debian compatível**,
ordenando pela data de publicação. Não aceita pacotes duplicados/ambíguos nem
uma edição parcial se algum repositório falhar. Todos os `.deb` compatíveis da
release selecionada são anunciados: não anexe ali pacotes opcionais que não devam
integrar a novidade. Não publique variantes `all`/`amd64` concorrentes do mesmo
pacote na mesma release.

Uma nova release estável compatível aparece na próxima consulta, sem recompilar
o Atualizador ou informar versões/IDs/hashes manualmente. Publicar essa release
na organização oficial é a aprovação editorial para distribuição. Não substitua
arquivos/tags de versões já distribuídas; publique uma versão nova.

## Verificações e limites

O aplicativo resolve main para um commit e lê ambos os arquivos nessa referência.
Repositórios e URLs de download pertencem à organização oficial Mainuan, usando
HTTPS. Redirecionamentos da API são bloqueados. Downloads podem seguir apenas
para o CDN de assets do GitHub, sem enviar credenciais.

Registra repositório, release, commit da tag, asset, tamanho, versão, arquitetura e
SHA-256. Esses dados ficam fixos durante a operação. Substituir a identidade/bytes
da mesma versão ou retroceder versões já observadas bloqueia a consulta. Uma
máquina nova depende da situação atual da conta oficial: não existe assinatura
criptográfica independente do GitHub neste canal.

A consulta não baixa `.deb`. O clique em Instalar novidades inicia a verificação
de InstallFiles, download com progresso, SHA-256 e metadados internos. Pacotes
instalados/configurados na versão anunciada ou superior ficam como recebidos.
Pacotes retidos ou incompletamente configurados bloqueiam a operação.

O planejador verifica dependências e simula todos os efeitos pelo PackageKit.
Somente os pacotes/versões anunciados e pendentes podem ser alterados. Dependências
adicionais, remoções, reinstalações e downgrades são bloqueados. Não existe
fallback para extração na raiz ou instalação por comandos fornecidos remotamente.

O clique inicial confirma uma operação idêntica aos recursos anunciados. Plano,
simulação e integridade são revalidados antes de InstallFiles real. O PolicyKit
solicita autorização nativa, sem captura de senha pelo aplicativo. Essa API
autoriza a transação após o download; não se cria solicitação artificial de senha.
**HTTPS e SHA-256 não equivalem à assinatura de um repositório APT.** Advertências
nativas de origem não confiável permanecem visíveis. O sucesso exige observação
das versões realmente instaladas.

`--check` aguarda 60 segundos e consulta de hora em hora. Sessão Live ou não
identificada não consulta o GitHub nem oferece instalação. Nunca instala sozinho.
Histórico, visualização e adiamento de 24 horas são separados do estado instalado.
O cache em `~/.local/state/mainuan-recursos/` conserva as últimas 50 edições para
consulta offline; sem conexão, a instalação é bloqueada. Falhas de validação não
substituem o último cache válido. Limites da API pública são tratados como
indisponibilidade de consulta, sem solicitar tokens.

## Infraestrutura histórica

`publish-resources.yml` não possui gatilho push/schedule e seu job está
incondicionalmente desativado. Alterar os dois arquivos não executa assinaturas,
GitHub Apps nem publicação APT. Configurações antigas não são lidas pelo modo
normal. Documentos anteriores de ativação dessa infraestrutura são históricos.

## Teste prático final

Na VM Mainuan com snapshot, após instalar o pacote 0.2.2 e conferir SHA256SUMS:

```bash
mainuan-atualizador-recursos
```

Deve apresentar mensagem e Gestão de Drivers 1.0 sem argumentos especiais. Se o
gestor ainda não estiver instalado, teste primeiro o cancelamento do PolicyKit e,
depois, a instalação autorizada. Confira o resultado sem abrir o gestor:

```bash
dpkg-query -W -f='${Package} ${Version} ${Status}\n' mainuan-gestao-drivers
```

Esperado: `mainuan-gestao-drivers 1.0 install ok installed`. Verificar novamente
deve reconhecer o recurso recebido. Não execute o gestor nem instale drivers
nesse ensaio. Restaure o snapshot para repetir o ciclo limpo.
