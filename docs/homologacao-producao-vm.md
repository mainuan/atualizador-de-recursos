# Instalação real em VM descartável

Este roteiro usa **somente chaves e pacotes de teste**. Não configura produção.
Os comandos com sudo/instalação são exclusivos da VM, nunca do sistema principal.
Não foi executada uma instalação real nesta entrega; esta é a matriz reproduzível
que o responsável precisa executar e registrar antes de liberar a produção.

## 1. Criar uma VM restaurável

Use uma instalação normal da ISO Mainuan alvo, Plasma 6/Wayland, usuário normal
com sudo e agente PolicyKit KDE. Prefira 2 GiB de RAM. Instale na VM as ferramentas
de teste que faltarem: `python3`, `python3-cryptography`, `python3-apt`, `dpkg-dev`,
`gnupg`, `openssl`, `ca-certificates` e `curl`. O `.deb` do aplicativo resolve suas
próprias dependências pelos repositórios normais da imagem.

Depois de comprovar a restauração, instale as ferramentas ausentes **somente na VM**:

```bash
sudo apt-get update
sudo apt-get install python3 python3-cryptography python3-apt dpkg-dev gnupg \
  openssl ca-certificates curl bubblewrap
```

Desligue a VM, crie snapshot **A-limpa** incluindo todos os discos mutáveis,
ligue-a e crie um arquivo canário. Restaure o snapshot pelo hypervisor e confirme
que o arquivo desapareceu. Só continue após essa prova. Anote nome/id do snapshot,
ISO, `/etc/os-release`, arquitetura, RAM, versão do Plasma e tipo de sessão:

```bash
cat /etc/os-release
dpkg --print-architecture
printf '%s\n' "$XDG_SESSION_TYPE"
```

Resultado esperado: instalação normal compatível, sessão `wayland`. Não prosseguir
numa sessão Live, num container ou sem restauração comprovada.

## 2. Gerar e conferir um kit novo

Copie o checkout revisado e o `.deb` para a VM. Sem credenciais oficiais, na raiz
do checkout **da VM**, gere um diretório novo:

```bash
/usr/bin/python3 tools/prepare-vm-kit.py --output /tmp/mainuan-kit-vm
/usr/bin/python3 tools/probe-vm-kit.py /tmp/mainuan-kit-vm \
  --output /tmp/mainuan-kit-vm/validacao-isolada.json
```

O segundo comando exige `bubblewrap`. Alternativamente, o kit e seu probe podem
ser preparados no ambiente de desenvolvimento: eles só geram arquivos e usam APT
isolado com host somente leitura. A instalação dos passos seguintes é só na VM.

Resultado esperado: duas edições assinadas (1/2), repositórios GPG válidos e seis
DEBs (três por versão), sem scripts ou executáveis. Os pacotes são
`mainuan-homologacao-alpha`, `-beta`, `-gamma`, versões 1.0 e 2.0, arquitetura `all`,
com pins SHA-256 no catálogo. Cada um acrescenta apenas um texto sob
`/usr/share/mainuan-homologacao/`. O probe confere assinaturas, payload, solver e
locks exclusivamente na raiz APT temporária, sem instalar.

As chaves privadas de assinatura do kit são descartadas depois de gerar as duas
edições. `tls/servidor.key` é somente a chave do servidor HTTPS de teste; nenhuma
chave oficial participa. A validade do kit/CA é de **dois dias** em UTC. Se expirou,
gere outro kit e restaure uma VM limpa; não ignore expiração ou TLS.

## 3. Instalar o aplicativo e o servidor local na VM

Na VM, ajuste o caminho do `.deb` ao arquivo copiado:

```bash
sudo apt-get install ./dist/mainuan-atualizador-recursos_0.2.0_all.deb
sudo install -d -m 0755 /opt/mainuan-homologacao
sudo cp -a /tmp/mainuan-kit-vm/. /opt/mainuan-homologacao/
sudo chown -R root:root /opt/mainuan-homologacao
sudo chmod 0755 /opt/mainuan-homologacao
sudo cp -a /opt/mainuan-homologacao/repo-v1 /opt/mainuan-homologacao/site/apt
sudo install -m644 /opt/mainuan-homologacao/tls/ca-teste.crt \
  /usr/local/share/ca-certificates/mainuan-homologacao.crt
sudo update-ca-certificates
printf '%s\n' '127.0.0.1 homologacao.mainuan.test' | sudo tee -a /etc/hosts
sudo install -Dm644 /opt/mainuan-homologacao/repo-chave-teste.asc \
  /etc/apt/keyrings/mainuan-homologacao.asc
sudo install -m644 /opt/mainuan-homologacao/config-homologacao.json \
  /etc/mainuan/atualizador-recursos.json
```

Em um segundo terminal **da VM**, mantenha o servidor aberto:

```bash
sudo /usr/bin/python3 /opt/mainuan-homologacao/servir-catalogo.py
```

Para os ensaios de logout/login ou reinício, use em vez desse terminal um serviço
**somente da VM**. Primeiro pare o servidor de terminal com Ctrl+C, para liberar
a porta 443, e então:

```bash
sudo tee /etc/systemd/system/mainuan-homologacao-https.service > /dev/null <<'UNIT'
[Unit]
Description=HTTPS descartavel de homologacao Mainuan
After=network.target

[Service]
ExecStart=/usr/bin/python3 /opt/mainuan-homologacao/servir-catalogo.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable --now mainuan-homologacao-https.service
sudo systemctl is-active mainuan-homologacao-https.service
```

Resultado esperado: `active`, serviço atendendo só em loopback e persistindo após
logout/reinício. Para indisponibilidade do passo 8, use `sudo systemctl stop
mainuan-homologacao-https.service`; para retomar, `sudo systemctl start
mainuan-homologacao-https.service`. O snapshot final remove essa unidade também.

Ele atende só `127.0.0.1:443`, sem CGI, e serve arquivos estáticos do kit. Não
precisa ser exposto à rede. Confirme TLS **sem** `-k`:

```bash
curl --fail https://homologacao.mainuan.test/catalog/novidades.json \
  --output /tmp/mainuan-catalogo-teste-recebido.json
```

Resultado esperado: JSON recebido com TLS validado pela CA de teste da VM.
A leitura por curl não autentica o catálogo: isso será feito pelo aplicativo.

## 4. Configurar o APT de teste por HTTPS

No primeiro terminal da VM:

```bash
printf '%s\n' 'deb [signed-by=/etc/apt/keyrings/mainuan-homologacao.asc] https://homologacao.mainuan.test/apt/ ./' \
  | sudo tee /etc/apt/sources.list.d/mainuan-homologacao.list
sudo apt-get update
apt-cache policy mainuan-homologacao-alpha mainuan-homologacao-beta mainuan-homologacao-gamma
```

Resultado esperado: índices assinados aceitos, candidatos 1.0, pacotes ainda não
instalados. Não usar `trusted=yes`, `--allow-unauthenticated`, exceção TLS, remoção
de locks ou política Polkit permissiva. Se PackageKit tiver índices antigos,
aguarde/atualize pelo mecanismo normal da imagem e confirme os candidatos.

Registre checkpoint **B-preparada** sem recursos instalados. Caso desligue/restaure
a VM, reinicie o servidor do passo 3 antes de consultar o catálogo ou APT. O
checkpoint não substitui o snapshot limpo A, que será usado ao final.

## 5. Conferir apresentação e cancelar a autenticação

Abra o aplicativo **como usuário normal**, sem `--demo`, sem sudo e sem flags de
catálogo local. A configuração do passo 3 escolhe o servidor de homologação.
Para isolar o estado deste ensaio, use sempre o mesmo diretório:

```bash
XDG_STATE_HOME="$HOME/.local/state/mainuan-homologacao-vm" mainuan-atualizador-recursos
```

Resultado esperado: edição 1, três recursos pendentes. Abrir “Conhecer novidades”
abre a página oficial indicada e só marca visualização. Prepare “Instalar
novidades”, confira o plano e confirme. Cancele no **agente PolicyKit do Plasma**.

Resultado esperado: erro/cancelamento sem sucesso falso. Confira:

```bash
dpkg-query -W -f='${binary:Package} ${Status} ${Version}\n' \
  mainuan-homologacao-alpha mainuan-homologacao-beta mainuan-homologacao-gamma
```

Antes de instalar, pacote ausente pode gerar retorno diferente de zero no
`dpkg-query`; isso é esperado. Nenhum deve aparecer como `install ok installed`.
O aplicativo não deve conter campo próprio de senha. Não gravar a digitação nem
incluir credenciais nos logs. Não modificar Polkit para forçar aprovação.

## 6. Reconhecer instalação externa e autorizar pelo PackageKit

Feche a janela. Na VM, instale só o alpha pelo APT:

```bash
sudo apt-get install mainuan-homologacao-alpha
```

Reabra com o mesmo comando do passo 5. Resultado esperado: alpha **Já recebido**,
beta/gamma pendentes. Isso comprova detecção de pacote configurado por outro meio.

Agora prepare/confirme no aplicativo e **autorize pelo agente PolicyKit real**.
Acompanhe o progresso e a mensagem final. Repita o `dpkg-query`: os três devem
estar `install ok installed`, versão 1.0. Reabrir o anúncio não deve oferecer
reinstalar os três; “Instalar novidades” deve ficar indisponível para esse plano.
Marcar visualização ou adiar nunca substitui essa leitura real do dpkg.

Se a autenticação estiver em cache e não houver diálogo, registre isso; restaure
B e repita a variante de cancelamento antes de uma autorização bem-sucedida.
Não aprove “cancelamento testado” sem ter visto/cancelado o agente real.

## 7. Segunda edição, falha de download e recuperação

Com o aplicativo fechado e sem outra operação de pacotes, substitua o conteúdo
servido pelo repositório v2, preservando v1 para diagnóstico:

```bash
sudo mv /opt/mainuan-homologacao/site/apt /opt/mainuan-homologacao/site/apt-v1
sudo cp -a /opt/mainuan-homologacao/repo-v2 /opt/mainuan-homologacao/site/apt
sudo cp /opt/mainuan-homologacao/edicoes/novidades-v2.json \
  /opt/mainuan-homologacao/site/catalog/novidades.json
sudo cp /opt/mainuan-homologacao/edicoes/novidades-v2.json.sig \
  /opt/mainuan-homologacao/site/catalog/novidades.json.sig
sudo apt-get update
sudo mv /opt/mainuan-homologacao/site/apt/pool/mainuan-homologacao-beta_2.0_all.deb \
  /opt/mainuan-homologacao/site/apt/pool/mainuan-homologacao-beta_2.0_all.deb.indisponivel
```

A source HTTPS permanece igual; o índice v2 continua assinado, mas falta um
artefato. Não instalar/download v2 antes dessa variante; use checkpoint se
houver um `.deb` v2 já em cache. Reabra com o mesmo estado do passo 5, aceite
edição 2 e tente instalar. Resultado esperado: falha de preparação/download ou da
transação, sem confirmação indevida. Pode haver resultado parcial: anote o dpkg
real, não presuma rollback automático. Não mate dpkg para fabricar falha.

Restaure o artefato e repita:

```bash
sudo mv /opt/mainuan-homologacao/site/apt/pool/mainuan-homologacao-beta_2.0_all.deb.indisponivel \
  /opt/mainuan-homologacao/site/apt/pool/mainuan-homologacao-beta_2.0_all.deb
```

Resultado esperado: instalação/atualização via PackageKit concluída, os três
configurados em 2.0 e sem nova reinstalação quando abrir outra vez.

## 8. Assinatura inválida, replay e rede

Feche a janela antes de trocar o par servido. Depois de ter aceitado a sequência
2, copie o par v1 para `site/catalog/novidades.json[.sig]` como no passo 7, usando
`novidades-v1.json`/`.sig`. Reabra sem alterar o diretório de estado.
Resultado esperado: catálogo antigo recusado. Volte ao par v2 original.

Para adulteração, acrescente um espaço ao JSON servido sem tocar a assinatura:

```bash
printf ' ' | sudo tee -a /opt/mainuan-homologacao/site/catalog/novidades.json > /dev/null
```

Reabra: assinatura inválida, nenhuma instalação liberada. Restaure o par v2
original com os dois comandos `sudo cp` do passo 7. Encerre só o servidor HTTPS
com Ctrl+C para testar indisponibilidade: cache ainda válido pode permitir
consulta, mas não instalar. Não pare um gerenciador de pacotes em transação.

## 9. Concorrência e integração

Restaure B para cada variante necessária. Pode-se manter uma operação benigna
ocupando o lock por 20 segundos **na VM**:

```bash
sudo apt-get -o DPkg::Pre-Invoke::='sleep 20' install mainuan-homologacao-alpha
```

Durante a espera, tente preparar/confirmar no aplicativo. Resultado aceitável:
aguardar lock, comunicar impedimento ou exigir novo plano após mudança de estado.
Não contornar lock. Faça também uma operação de pacote de teste no Discover,
sem iniciar uma atualização geral para fabricar concorrência.

Confira menu, ícone, autostart após login, instância única, temas claros/escuros,
Blur-Glassy e consumo total com 2 GiB. Uma sessão Live deve impedir autostart e
instalação de recursos. Registre separadamente os resultados não executados.
O serviço HTTPS precisa estar aberto nos ensaios de login ou deve ocorrer falha
segura de rede; não confundir essa falha com problema de autostart.

### Menu, autostart e uma instância

Feche a janela usada com `XDG_STATE_HOME` personalizado. Esses testes devem usar
o comando normal e o diretório padrão, como o autostart, sem sobrescrever essa
variável. Não trate duas configurações XDG diferentes como teste de instância única.

1. Abra pelo menu do Plasma procurando “Mainuan”; confira nome, ícone e janela.
2. Feche a janela, faça logout/login real no KDE, com o servidor HTTPS em serviço.
   Espere pelo menos 90 s antes de concluir que a primeira consulta não ocorreu.
   Se a novidade já foi vista nesse usuário, a janela pode continuar oculta:
   o processo de sessão e a consulta devem ocorrer mesmo assim.
3. Consulte os logs de requisições locais e a lista de processos:

   ```bash
   sudo journalctl -u mainuan-homologacao-https.service -b --no-pager
   ps -u "$(id -u)" -o pid,etime,args | rg 'mainuan-atualizador-recursos'
   ```

   Desconsidere a linha do próprio `rg`. Registre horário de login e primeira
   requisição, esperada aproximadamente 60 s após iniciar o processo de sessão.
4. Abra o menu duas vezes e execute `mainuan-atualizador-recursos` em outro
   terminal. Resultado esperado: mesma janela/PID de sessão, sem duas instâncias
   permanentes, sem operações paralelas nem perda de histórico.
5. Dentro da VM, aplique os temas claro/escuro e Blur-Glassy nas Preferências do
   Sistema. Confira texto, botões, diálogos, decoração do KWin e escala 640×480.
   Registre tema realmente instalado; simular somente a paleta não aprova decoração.

### Sessão Live real

Inicialize a ISO Mainuan em outra VM descartável, em “Experimentar”, e registre
`cat /proc/cmdline`. A aplicação precisa estar presente para o teste ser válido.
Se a ISO ainda não a inclui, instale **apenas o aplicativo candidato** nessa VM
Live (overlay temporário), a partir do `.deb` copiado:

```bash
sudo apt-get install ./dist/mainuan-atualizador-recursos_0.2.0_all.deb
mainuan-atualizador-recursos --check
printf 'Retorno do autostart: %s\n' "$?"
mainuan-atualizador-recursos
```

Resultado esperado: `--check` retorna 0 sem janela de novidade; execução manual
explica a sessão Live e não oferece instalar recursos. Não instalar os três
recursos nesse teste. Faça logout/login na sessão KDE Live sem reiniciar a VM,
para preservar o overlay que contém o aplicativo, e confira que o autostart não
abre a janela de novidades nem deixa um processo residente do atualizador.
Se faltarem dependências/ISO apropriada, marque **não executado**, não aprovado.

### VM limitada a 2 GiB

Desligue a VM antes de ajustar a RAM para 2048 MiB no hypervisor. Ligue, use
Plasma/Wayland e os mesmos testes. Sem aumentar a RAM para esconder uma falha,
registre `free -m` e identifique o PID real do aplicativo pela lista acima.
Substitua o número abaixo pelo PID observado:

```bash
APP_PID=1234
cat /proc/"$APP_PID"/smaps_rollup
ps -p "$APP_PID" -o pid,rss,pcpu,etime,args
sudo journalctl -b -k --no-pager | rg -i 'oom|out of memory|killed process'
```

Registre PSS/RSS em repouso, durante consulta e instalação. Para CPU em uma janela
de 30 s, use o Monitor do Sistema do Plasma com o processo selecionado; `%CPU`
do `ps` é uma média desde o início, não substitui essa janela. Anote tempos de
resposta ao selecionar o histórico/abrir diálogos e qualquer congelamento maior
que 2 s. Observe pelo menos cinco minutos de repouso para crescimento de memória.
Compare com os critérios em [versao-candidata.md](versao-candidata.md). Resultado
sem linhas de OOM é esperado; retorno vazio do `rg` nesse caso não é falha.

## 10. Registrar e limpar por restauração

Use uma tabela com teste, resultado esperado, resultado obtido, evidência e
passou/falhou/não executado. Inclua versões dpkg, horário/UTC, ISO/snapshot,
versão do `.deb`, memória, qual agente de autenticação apareceu e mensagens de
falha. Evite logs com credenciais. Exporte somente evidências e restaure A-limpa.

Resultado esperado final: CA, domínio local, source, keyrings, pacotes e estado
de teste deixam de existir. Nenhuma confiança descartável deve ir para uma ISO
ou canário oficial. Aprovar esta matriz é pré-requisito do passo 4 do
[guia de configuração inicial](configuracao-inicial-producao.md).
