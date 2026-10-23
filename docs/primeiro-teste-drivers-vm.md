# Primeiro teste real — Gestão de Drivers 1.0

Este kit instala **somente o aplicativo** `mainuan-gestao-drivers=1.0`, pela interface
do Atualizador instalado e por PackageKit/PolicyKit. Não execute o Gestão de Drivers
nem instale drivers neste ensaio. Não execute estes passos no computador principal.

O kit expira em **48 horas a partir da geração**. Consulte `kit.json` para os horários
UTC exatos. Se expirar, gere outro kit; não altere relógio, assinaturas ou validade.
As chaves Ed25519 do catálogo e GPG do APT são descartáveis e distintas das oficiais.
Suas partes privadas foram descartadas. A única chave privada transferida é a do
servidor HTTPS local, também descartável e válida por 48 horas. Não publique o kit.

## 1. Snapshot obrigatório, antes de qualquer configuração

Na VM Mainuan instalada, feche Atualizador, Discover e qualquer operação de APT.
Não execute atualizações gerais durante o ensaio. Confira `timedatectl`: data e hora
precisam estar corretas. A VM precisa ter o Atualizador 0.2.0 instalado e o agente
PolicyKit da sessão Plasma funcionando.

Desligue a VM. No GNOME Boxes, abra suas preferências/propriedades, encontre
**Snapshots** e crie `antes-gestor-1.0`. Confirme que consegue restaurá-lo: inicie a
VM, crie `~/marcador-snapshot.txt`, desligue, restaure o snapshot e inicie novamente.
O arquivo deve ter desaparecido e o Atualizador deve continuar instalado.
Se a edição do Boxes não oferecer snapshots, use uma cópia restaurável do disco
virtual feita com a VM desligada e teste a restauração antes de prosseguir.

Não prossiga sem restauração comprovada. Os scripts registram o nome informado;
não conseguem verificar o snapshot administrado pelo computador anfitrião.

## 2. Transferir e conferir

Transfira estes **dois arquivos** para `~/Downloads` da VM usando o mecanismo de
transferência/compartilhamento do Boxes ou um pendrive virtual:

- `kit-mainuan-gestor-1.0.tar.gz`
- `kit-mainuan-gestor-1.0.tar.gz.sha256`

Alternativa, se o SSH já estiver configurado na VM, execute no computador anfitrião,
na pasta que contém esses arquivos, trocando usuário e IP:

```bash
scp kit-mainuan-gestor-1.0.tar.gz kit-mainuan-gestor-1.0.tar.gz.sha256 usuario@IP_DA_VM:Downloads/
```

A partir daqui, **todos os comandos são executados no terminal da VM**:

```bash
cd ~/Downloads
sha256sum -c kit-mainuan-gestor-1.0.tar.gz.sha256
tar -xzf kit-mainuan-gestor-1.0.tar.gz
cd kit-mainuan-gestor-1.0
/usr/bin/python3 vm.py inspecionar > inspecao.txt
less inspecao.txt
```

Resultado esperado: checksum `OK`, catálogo/autenticação e assinaturas APT válidos;
um único pacote, `mainuan-gestao-drivers`, versão `1.0`, arquitetura `all`.
Compare também o SHA externo com o fornecido junto à entrega por um canal confiável.
Um checksum transportado junto ao arquivo detecta corrupção, não substitui esse vínculo.

Confira livremente, sem executar nada do pacote:

```bash
dpkg-deb --field apt/pool/mainuan-gestao-drivers_1.0_all.deb
dpkg-deb --contents apt/pool/mainuan-gestao-drivers_1.0_all.deb
less auditoria-pacote.json
```

O SHA-256 aprovado do `.deb` é:

```text
d7a1c98743a204f6b5770c7746cb02b3b4d66c09d2d368966118ac39fa47b912
```

Origem: [release oficial v1.0](https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.0),
release ID `421218277`, asset ID `667222935`, 190846 bytes. O hash foi comparado com
a API GitHub e com `SHA256SUMS` publicado. Isso comprova a correspondência com o
artefato obtido por HTTPS; não constitui assinatura oficial do fornecedor nem
atestação de compilação. A release não está marcada como imutável no GitHub.
O kit fixa os bytes aprovados, versão, arquitetura, IDs e commit observado
`d84fdd9c75acca7c69e3e07912f4f0f064b4d1e7`; não acompanha alterações da tag.

Dependências declaradas: `python3 (>= 3.7)`, `python3-pyqt6`, `qt6-svg-plugins`,
`python3-apt`, `ubuntu-drivers-common`, `packagekit`. Recomendados: `mokutil`,
`openssl`, `kmod`. **Não serão instalados/atualizados neste primeiro ensaio**.
O APT precisa conseguir satisfazer as dependências com as versões já instaladas.
Se faltar alguma, a preparação falhará, mostrará o diagnóstico e restaurará a
configuração. Guarde a mensagem; não use `apt --fix-broken`, `--allow-unauthenticated`,
`trusted=yes` ou atualizações gerais para forçar a continuidade.

Os quatro scripts do pacote apenas tratam a remoção de uma antiga regra sudoers do
próprio aplicativo. O kit exige que essa regra esteja ausente. O payload não contém
módulos, firmware, DKMS, serviços nem autostart. Sua instalação não executa o gestor.
O pacote possui código capaz de gerenciar drivers quando executado: não o abra.

## 3. Configurar exclusivamente o ambiente experimental

Ainda na pasta extraída, com o snapshot já criado e testado:

```bash
sudo /usr/bin/python3 vm.py preparar --snapshot-confirmado antes-gestor-1.0
```

Se usar uma cópia restaurável do disco, informe o nome dessa cópia no lugar do nome
do snapshot. A configuração recusa computador físico, sessão Live/desconhecida,
gestor já instalado, produção com chaves configuradas e pacote inconsistente no dpkg.

O inventário inicial de módulos/firmware é feito somente por leitura e pode levar
alguns minutos. Aguarde sua conclusão; os arquivos são lidos em blocos, sem carregar
todo o firmware na memória.

O comando copia o kit para `/opt/mainuan-homologacao-drivers`, guarda a configuração
original, registra pacotes e hashes de arquivos de hardware e configura:

- APT **local** `file:/opt/mainuan-homologacao-drivers/apt`, com `signed-by` apontando
  apenas para a chave descartável. As demais fontes não são apagadas.
- Política APT temporária que permite somente o gestor deste repositório e bloqueia
  candidatos novos de todos os outros pacotes. As preferências anteriores são
  guardadas para restauração. Não utilize APT/Discover para outros fins enquanto
  essa política estiver ativa.
- Atualização **somente do índice do repositório experimental**, preservando os
  índices das fontes normais, e simulação APT, sem instalação.
- Catálogo assinado em `https://homologacao.mainuan.test/catalog/novidades.json`,
  servido exclusivamente em `127.0.0.1:443` por uma unidade systemd temporária.
- Configuração experimental do Atualizador em `/etc/mainuan/atualizador-recursos.json`,
  com backup exato da configuração original desativada.

Não são instalados certificados globais. O certificado de testes será confiado
somente pelo processo aberto pelo kit. O serviço não é habilitado no boot.
Não reinicie a VM nem faça logout com a configuração experimental ativa.
Feche qualquer outra instância do Atualizador para evitar o bloqueio de instância única.

Resultado esperado: simulação contendo **somente** `Inst mainuan-gestao-drivers (1.0 ...)`.
Erros de lock não são contornados: aguarde a operação terminar e restaure o snapshot
antes de repetir uma preparação incompleta. Se a preparação falhar após criar a
pasta em `/opt`, mantenha os backups/evidências e retorne ao snapshot para recomeçar.

## 4. Conferir o plano real do PackageKit, antes da instalação

Como usuário comum, **sem sudo**:

```bash
/usr/bin/python3 /opt/mainuan-homologacao-drivers/vm.py plano
```

O comando consulta o catálogo via HTTPS, valida sua assinatura e usa o mesmo
controlador do Atualizador para resolver os pacotes e simular pelo PackageKit.
Ele **nunca confirma uma transação real**. Só aprova um efeito: instalar
`mainuan-gestao-drivers;1.0;all`. Dependência, atualização, remoção ou efeito adicional
interrompe o ensaio. O plano aprovado fica no diretório de estado exclusivo do teste.

Se o PackageKit não enxergar o pacote, feche Discover/Atualizador, aguarde o daemon
ficar ocioso e tente `plano` novamente. Guarde a mensagem se persistir. Não mate
APT/dpkg, não remova locks e não altere o catálogo para contornar a falha.

## 5. Abrir o Atualizador e instalar pela interface

```bash
/usr/bin/python3 /opt/mainuan-homologacao-drivers/vm.py abrir
```

Este comando abre **o aplicativo instalado**, como usuário comum, **sem `--demo`**.
Não simula a instalação. O histórico, adiamentos e controle de sequência ficam
isolados em `~/.local/state/mainuan-homologacao-drivers-<id-do-kit>/`.

1. Confira que aparece apenas **Gestão de Drivers 1.0**.
2. **Conhecer novidades** deve abrir a release oficial no navegador padrão.
3. Clique **Instalar novidades** e leia todos os detalhes da operação. Deve haver
   somente a instalação do gestor 1.0, sem drivers ou outras alterações.
4. Cancele primeiro a confirmação do aplicativo: nada deve ter sido instalado.
5. Repita e confirme. Quando o **agente PolicyKit do Plasma** solicitar autorização,
   cancele. O aplicativo deve informar cancelamento/falha, sem declarar conclusão.
   Confira `dpkg-query` conforme abaixo e execute `plano` novamente antes de retentar.
6. Repita e autorize no agente do sistema. Observe progresso e confirmação real de
   conclusão. Nenhuma senha é solicitada, capturada ou armazenada pelo kit/Atualizador.
7. **Não abra o Gestão de Drivers**, não clique em instalar/remover drivers nem
   aceite atualizações gerais no Discover.

O PolicyKit pode reutilizar uma autorização temporária já concedida. Se não surgir
um diálogo, não considere o teste de cancelamento aprovado: restaure o snapshot ou
encerre a sessão antes de configurar novamente. Não enfraqueça a política do sistema.
Se a confirmação listar qualquer pacote adicional, cancele e guarde a evidência.

## 6. Verificar o resultado

```bash
dpkg-query -W -f='${Package} ${Version} ${Architecture} ${Status}\n' mainuan-gestao-drivers
sudo /usr/bin/python3 /opt/mainuan-homologacao-drivers/vm.py verificar
```

Esperado: `mainuan-gestao-drivers 1.0 all install ok installed` e somente esse pacote
adicionado. A verificação compara também arquivos de módulos, firmware, DKMS,
configurações de boot e nomes dos módulos carregados. Não instala nem executa nada.
Mudanças devem ser investigadas e o snapshot restaurado; um módulo carregado por
uma ação externa pode produzir diferença e precisa de análise.

O relatório fica em `/opt/mainuan-homologacao-drivers/resultado.json`. Com a interface
ainda aberta, execute a verificação manual no menu: deve reconhecer o recurso como
já recebido, sem oferecer reinstalação. Se fechou, repita o comando `abrir` após
`plano` (que reconhecerá recursos já recebidos); siga as instruções impressas.
Abrir artigo ou visualizar a novidade não pode marcar o recurso como instalado.

Para guardar evidências antes de restaurar a VM:

```bash
sudo journalctl -u mainuan-homologacao-drivers.service -u packagekit.service --since today > ~/Downloads/servicos-homologacao.txt
sudo cat /opt/mainuan-homologacao-drivers/resultado.json > ~/Downloads/resultado-homologacao.json
```

Transfira esses arquivos e capturas dos diálogos ao computador anfitrião. Não
registre senhas. Anote explicitamente quais cenários foram de fato executados.

## 7. Restaurar e remover a configuração experimental

Feche o Atualizador. Dentro da VM:

```bash
sudo /usr/bin/python3 /opt/mainuan-homologacao-drivers/vm.py limpar
```

O comando para o servidor, restaura `/etc/hosts`, configuração original do
Atualizador e preferências APT e remove fonte, chave e índices exclusivamente
experimentais. Havendo alteração externa conflitante, preserva o backup e pede
restauração do snapshot. A pasta do kit e seus relatórios permanecem para inspeção.

**Limpar a configuração não desinstala o gestor.** Para desfazer a instalação e
recuperar integralmente o estado anterior (inclusive caches e registros), desligue a
VM e restaure `antes-gestor-1.0` no Boxes. Esse é o procedimento recomendado.
Não execute `autoremove`. Depois da restauração, confirme ausência do gestor e que
`/etc/mainuan/atualizador-recursos.json` voltou a ter `"keys": {}`.
Apague apenas os arquivos transferidos e o estado do kit, se ainda existirem:

```bash
rm -r -- ~/Downloads/kit-mainuan-gestor-1.0
rm -- ~/Downloads/kit-mainuan-gestor-1.0.tar.gz ~/Downloads/kit-mainuan-gestor-1.0.tar.gz.sha256
```

Se optar por conservar a instalação do gestor na VM e apenas limpar o ensaio,
após conferir a restauração remova explicitamente a pasta do kit e o diretório de
estado correspondente ao `id` de `kit.json`. Conserve uma cópia das evidências antes:

```bash
sudo rm -r -- /opt/mainuan-homologacao-drivers
```

## Escopo da aprovação

O kit não declara PackageKit/PolicyKit, tema ou instalação na sua VM como aprovados.
Esses resultados dependem da execução acima. Este primeiro teste exclui dependências
novas, atualizações gerais, concorrência forçada, login/autostart, sessão Live e
gestão efetiva de drivers. Produção permanece desativada e sem chaves oficiais.

Para regenerar localmente, sem instalar no anfitrião, usando a cópia aprovada do `.deb`:

```bash
/usr/bin/python3 tools/prepare-drivers-vm-kit.py --deb dist/homologacao-gestao-drivers-1.0/mainuan-gestao-drivers_1.0_all.deb --output dist/nova-rodada/kit-mainuan-gestor-1.0
```

Use um diretório de saída novo. O gerador usa as ferramentas já existentes de
homologação, gera novas chaves descartáveis e não consulta uma versão posterior
da release. O código do aplicativo, publicação e produção não é modificado.
