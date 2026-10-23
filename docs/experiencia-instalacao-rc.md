# Experiência de instalação — candidata local 0.2.1~rc1

Esta candidata mantém a janela clássica, a ilustração, o menu, o histórico e o
adiamento. A produção permanece desativada. Não foi publicada nem enviada ao GitHub.
O número Debian é maior que 0.2.0 e anterior a uma futura 0.2.1 estável, permitindo
atualizar a candidata já instalada na VM sem forçar reinstalação ou downgrade.

## O que mudou

Os botões permanecem verticais à direita, com dimensões e espaçamento iguais:
**Instalar novidades**, **Agora não**, **Conhecer novidades**. Instalar usa o botão
padrão nativo do Qt e texto em negrito. Agora não é um botão convencional, sem
`flat`; Conhecer continua disponível como ação opcional. Não há cores ou estilos
gráficos fixados pelo aplicativo. O foco inicial acompanha a instalação quando
ela se torna disponível.

A consulta GitHub inicial lê somente metadados, mensagem, programas e estado
instalado. Não baixa, cria nem examina o arquivo `.deb`. O download começa após
escolher instalar; arquivo previamente armazenado só é reutilizado após verificar
seu tamanho e hash. O pacote instalado em versão adequada não é baixado novamente.

O fluxo executa download, verificação de origem/integridade, conferência Debian e
dependências, simulação PackageKit, validação dos efeitos, revalidação do plano,
nova simulação e autorização real pelo sistema. Quando os efeitos correspondem
exatamente aos recursos anunciados, o clique inicial confirma a intenção, sem
outro diálogo do aplicativo. Efeitos adicionais seguros no fluxo normal continuam
exigindo confirmação explícita, com Cancelar como padrão. Efeitos não confiáveis,
remoções, downgrades e demais situações proibidas continuam bloqueados.

O modo GitHub deste primeiro ensaio continua limitado ao Gestão de Drivers 1.0.
Nele, dependências adicionais ou outros pacotes são bloqueados; não são liberados
por uma confirmação. Isso preserva o escopo de instalar somente o aplicativo.
Não execute o gestor nem faça alterações em drivers neste ensaio.

As mensagens normais são Preparando instalação..., Baixando novidades...,
Instalando novidades... e Concluído! Aproveite os novos recursos do Mainuan.
Download informa a porcentagem dos bytes recebidos; PackageKit informa seu próprio
progresso. Espera por outro gerenciador e autorização continuam identificáveis.
Conclusão só aparece após o PackageKit confirmar sucesso e o inventário Debian
confirmar a instalação. Cancelamentos e erros preservam o diagnóstico, sem sucesso
falso. Falha após a transação não provoca outro download durante a verificação.

SHA-256 e a explicação sobre o arquivo local/assinatura APT ficam em
**Mais opções → Informações técnicas**. Nenhum alerta real do PackageKit/PolicyKit
foi suprimido. Não há senha solicitada ou armazenada pelo aplicativo.

## Por que a autorização vem depois do download

O método nativo InstallFiles precisa receber um caminho existente e validar seu
tipo de conteúdo antes de chamar a autorização. A implementação oficial do daemon
faz essas verificações em `pk_transaction_install_files`, antes de
`pk_transaction_obtain_authorization`.
[Fonte: PackageKit 1.3.4](https://github.com/PackageKit/PackageKit/blob/v1.3.4/src/pk-transaction.c#L3729-L3775).

Portanto, com o `.deb` avulso do GitHub, o fluxo é clique → download/verificações →
PolicyKit → instalação. Não existe uma autorização genérica antecipada vinculada
a um arquivo ainda inexistente nesta API. Não usamos um diálogo artificial de
senha, autorização de outra ação administrativa ou alteração das políticas do
sistema. A preparação e a simulação não confirmam uma instalação real.

## Confiança oficial no futuro

O hash conhecido e o HTTPS vinculam o ensaio ao artefato oficial já examinado,
mas não transformam um `.deb` avulso em pacote de repositório APT autenticado.
O aviso real do sistema sobre instalação local não confiável pode continuar.
O aplicativo mantém a mesma API nativa de instalação local utilizada no primeiro
teste real, sem liberar pacotes arbitrários nem alterar opções globais do APT.

A solução preparada no projeto é publicar os mesmos `.deb` em um repositório APT
oficial com `InRelease` assinado. A chave pública e a fonte com `Signed-By` seriam
distribuídas uma única vez pela imagem/pacote de configuração do Mainuan. O backend
normal usaria InstallPackages com ONLY_TRUSTED, reconhecendo a origem oficial.
[Referência APT: Signed-By](https://manpages.debian.org/unstable/apt/sources.list.5.en.html#THE_DEB_AND_DEB-SRC_TYPES:_OPTIONS).

O publicador existente já gera índices, hashes e assinaturas a partir dos dois
arquivos editoriais, com credenciais protegidas no GitHub Actions. Depois da
configuração inicial e homologação dessa infraestrutura, cada publicação continua
exigindo apenas release aprovada, `packages.txt` e `message.txt`; sem assinar arquivos
ou editar JSON manualmente a cada novidade. Rotação de chaves e configuração de
produção continuam tarefas controladas, fora desta candidata. Nada foi ativado.

## Mesa/Zink e execução na VM

Não foi imposta renderização por software no launcher, no autostart ou no código.
Não foram modificados Mesa, drivers, arquivos de sessão ou configurações globais.
Se os avisos ocorrerem na VM, utilize somente para este processo:

```bash
env LIBGL_ALWAYS_SOFTWARE=1 GALLIUM_DRIVER=llvmpipe mainuan-atualizador-recursos --homologacao-github
```

As variáveis selecionam renderização por software e o driver Gallium llvmpipe,
conforme a [documentação oficial Mesa](https://docs.mesa3d.org/envvars.html).
Não redirecione/silencie todos os erros: avisos úteis precisam continuar disponíveis.
Esse comando não exporta as variáveis para outros aplicativos ou para a sessão.

## Instalar e conferir na VM

Restaure o snapshot anterior à instalação do Gestão de Drivers para observar o
novo download e a instalação. Se o gestor continuar instalado, o comportamento
correto é indicar o recurso já recebido e não reinstalá-lo.

Transfira o `.deb` e seu `.sha256` de `dist/experiencia-rc/` para `~/Downloads` da VM.
Feche o Atualizador e evite operações simultâneas do Discover/APT neste ensaio.
Execute **somente dentro da VM**:

```bash
cd ~/Downloads
sha256sum -c mainuan-atualizador-recursos_0.2.1~rc1_all.deb.sha256 &&
sudo apt install ./mainuan-atualizador-recursos_0.2.1~rc1_all.deb
mainuan-atualizador-recursos --version
mainuan-atualizador-recursos --homologacao-github
```

Esperado: versão `0.2.1~rc1`. Sem pacote baixado durante a consulta; após um único
clique em Instalar novidades, aparecem download, preparação, autorização PolicyKit
e instalação, sem confirmação intermediária para a operação exata. Teste também
cancelar a autorização e confira que não aparece conclusão falsa.

Se o snapshot conservar o `.deb` baixado pela candidata antiga, o arquivo íntegro
será reutilizado depois do clique. Para observar um download novo, com o Atualizador
fechado, remova somente esse cache de testes dentro da VM, preservando o histórico:

```bash
rm -f -- "${XDG_STATE_HOME:-$HOME/.local/state}/mainuan-recursos-homologacao-github/pacotes/mainuan-gestao-drivers_1.0_all.deb"
```

```bash
dpkg-query -W -f='${Package} ${Version} ${Architecture} ${Status}\n' mainuan-gestao-drivers
```

Após sucesso: versão 1.0, arquitetura all, install ok installed. Abra Informações
técnicas para os hashes e detalhes. Depois restaure o snapshot para desfazer o ensaio.
