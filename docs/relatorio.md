# Relatório de entrega — 22/10/2026

Este é o registro da implementação inicial. A etapa posterior de
[auditoria e homologação](homologacao.md) documenta as correções, 92 testes,
validação visual em Wayland e ciclo Debian isolado, além das pendências de VM.

O antigo aplicativo TigerOS Bash/YAD foi substituído por um canal de novidades
Python/PyQt6 Widgets para o Mainuan. O backend do PR #1 foi avaliado e não foi
integrado: ele acompanhava apenas upgrades de recursos instalados. Os padrões
de separação de camadas, worker, Live e adiamento foram considerados. A
arquitetura do Gestão de Drivers orientou a integração QtDBus/PackageKit e
PolicyKit, sem dependência entre os dois aplicativos.

## Como publicar uma novidade

Edite `catalogo/novidades.json`, adicione o lançamento, incremente `sequence`,
atualize as datas UTC e gere `novidades.json.sig` com `tools/catalog.py sign`.
O catálogo tem validade máxima de 31 dias e precisa de renovação periódica.
Publique JSON e assinatura juntos no processo autorizado da equipe, mantendo os
lançamentos anteriores para o histórico. Isso não exige mudar o código nem a
versão do aplicativo.

A URL de produção já é a solicitada, em
`raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json`.
**A produção continua desativada**: o catálogo inicial está vazio e sem
assinatura; `data/atualizador-recursos.json` não contém chave pública oficial.
A equipe precisa fornecer essa chave e provisioná-la pela configuração confiável
da distribuição. Nenhuma chave oficial foi gerada, presumida ou publicada.

O procedimento completo de assinatura, ativação, rotação e publicação está em
[publicacao.md](publicacao.md).

## Como informar programas e versões

Cada lançamento define `id`, `version`, `title`, `summary`, `article_url`,
`features` e, opcionalmente, `compatibility`. Cada recurso contém título
legível e pacotes com `name` e `min_version`. Essa é a lista explícita de programas
oferecidos. Não há filtro obrigatório por prefixo de nome nem exigência de
instalação prévia. Os nomes e versões do exemplo são fictícios.

A versão do anúncio identifica seu estado; a versão mínima do pacote define
quando ele já foi recebido. São conceitos separados.

## Como personalizar a matéria

Altere `article_url` no lançamento. Inicialmente, somente caminhos sob
`https://github.com/mainuan/` são aceitos, incluindo páginas de repositórios e
notas de lançamento. Outras contas, travessia de caminho, percent-encoding e
URLs fora dos prefixos autorizados falham na validação, mesmo quando assinadas.
Novos domínios/prefixos exigem alteração administrativa controlada da configuração.
O botão **Conhecer novidades** abre o navegador padrão por QDesktopServices.

## Como verifica e instala os pacotes

O manifesto é baixado com HTTPS, limite de tamanho, timeout e restrição de
redirecionamentos. A assinatura Ed25519 é conferida antes de interpretar os
lançamentos; esquema, validade, compatibilidade e sequência são validados.
Uma sequência já observada não pode retroceder ou mudar de conteúdo. A proteção
é por usuário e depende de preservar o estado local e o relógio correto.

APT é usado somente para leitura em worker: detecta versões configuradas,
candidatos e origens confiáveis. PackageKit resolve IDs exatos e simula a
instalação; todos os efeitos, inclusive dependências, são validados e apresentados
na confirmação. Remoções, reinstalações, downgrades e efeitos não reconhecidos
são bloqueados na preparação. Antes de instalar, o plano e a simulação são
repetidos; alterações exigem nova confirmação.

A transação real usa ONLY_TRUSTED e autorização interativa de PackageKit/PolicyKit
pelo agente do Plasma. O aplicativo não recebe senhas nem executa apt-get,
pkexec, scripts remotos ou TAR como root. Não adiciona repositórios. Falhas e
cancelamentos não produzem confirmação de sucesso. Depois de `Finished`, uma
nova leitura do dpkg confirma as versões e a configuração dos pacotes. Quedas
do daemon podem ter resultado parcial e são informadas dessa forma.

A simulação e a operação real não são atomicamente ligadas pelo PackageKit;
existe uma janela de concorrência com outros gerenciadores. Não há rollback
automático nem garantia de impedir toda mudança de dependências nessa janela.

## Como trata versões já instaladas

Versão instalada e configurada igual ou superior à mínima aparece como **Já
recebido**, mesmo se foi entregue pelo atualizador APT tradicional. Não é
reinstalada. Candidatos maiores não geram um upgrade adicional se a mínima do
anúncio já foi atendida. Versões antigas são atualizadas apenas se existir
candidato suficiente e confiável. Pacotes ausentes podem ser instalados.
Pacotes retidos, quebrados, indisponíveis ou sem origem confiável bloqueiam a
operação e mostram a razão.

## Notificações e histórico

Autostart KDE faz a primeira consulta após 60 segundos e repete a cada hora,
fora da thread gráfica. Sessão Live não faz consultas. Uma instância por usuário
mantém o estado; abrir pelo menu ativa a janela existente. Visualização,
adiamento por 24 horas e situação dos pacotes são independentes. Novidades já
visualizadas permanecem no histórico e não são repetidas automaticamente.
Cache autenticado ainda válido permite consulta offline, com instalação bloqueada.

## Como testar tudo sem alterar o sistema

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
```

Esse modo usa somente memória, inclusive na autorização e instalação. Para
validar também assinatura e arquivos locais, gere chaves descartáveis com
`tools/dev-catalog.py` e execute `--demo --test-catalog ... --test-config ...`.
Não acessa a configuração de produção. [testes.md](testes.md) traz todos os
cenários e comandos.

## Verificação realizada e limites

- 73 testes automatizados passando, incluindo fluxo completo de Widgets com
  confirmação, instalação simulada e conferência final da tabela.
- Geração e verificação de catálogo assinado com chave descartável; execução da
  entrada do aplicativo com catálogo local assinado, APT e D-Bus bloqueados.
- Consulta real **somente de leitura** `Resolve` no PackageKit por QtDBus; IDs,
  progresso e `Finished` recebidos. Nenhuma instalação real executada.
- Interface inspecionada em Qt offscreen; entradas desktop validadas.
  Traduções nativas Qt pt_BR carregadas para os diálogos e controles padrão.
- Pacote `.deb` construído sem root pelo script local e por debhelper; CI
  configurado para Ubuntu 26.04, testes e artefato, sem publicação de releases.
  Pacote validado com lintian sem avisos ou erros.

A instalação real com autorização PolicyKit, integração de sessão no Plasma 6
Wayland e aparência nos temas Dream/Blur-Glassy exigem a homologação em VM descrita
em [testes.md](testes.md). Não foram declaradas como verificadas neste ambiente.
O workflow foi preparado e o comando de construção validado localmente; não foi
executado remotamente. Nenhum commit, push, tag, release ou merge do PR #1 foi feito.
