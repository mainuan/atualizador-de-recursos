# Atualizador de Recursos do Mainuan (Qt6)

Nova versão do antigo atualizador YAD do TigerOS, reimplementada com **PyQt6 / Qt Widgets** para o **Mainuan (Kubuntu 26.04)**. Não utiliza YAD, `tiger-osd.sh`, `sudo -S`, pacotes TAR externos nem servidores do TigerOS.

## Objetivo e escopo

**Atualizador de Recursos**: acompanha apenas atualizações de pacotes **já instalados** cujos nomes começam com `mainuan-`, além dos pacotes adicionais explicitamente relacionados em `/etc/mainuan/atualizador-recursos.conf`. Não faz atualização geral da distribuição e, portanto, não substitui o Discover nem o notificador de atualizações do sistema.

Os recursos **precisam estar publicados em repositórios APT confiáveis configurados na máquina**. Este projeto não cria o repositório, não publica novos pacotes de recursos e não converte o pacote TAR legado em `.deb`. Sem pacotes elegíveis/novas versões disponíveis, a interface indicará que não há atualizações.

## Execução

- Menu de aplicativos: **Atualizador de Recursos**, executa uma verificação explícita.
- Autostart KDE: `mainuan-atualizador-recursos --check` faz verificação silenciosa e só abre a janela se existirem recursos atualizáveis; não executa na sessão Live e respeita adiamento de um dia ao clicar em **Depois**.
- **Verificar** consulta o cache APT local (sem solicitar senha).
- **Atualizar listas** solicita autorização via Polkit e executa `apt-get update`.
- **Instalar recursos** mostra a lista e solicita confirmação e autorização via Polkit. Usa `apt-get install --only-upgrade --no-remove` somente com os nomes retornados pelo APT; dependências necessárias também podem ser atualizadas/instaladas. Nenhuma alteração acontece sem ação do usuário.

### Pacotes fora do prefixo `mainuan-`

Edite `/etc/mainuan/atualizador-recursos.conf` (com privilégios de administrador) e adicione **um nome literal de pacote por linha**, sem argumentos. Por exemplo:

```text
welcome5
alerta-atualizacao
```

Esses nomes são meros exemplos: verifique se os pacotes realmente estão instalados e disponíveis no repositório apropriado. A ferramenta não gerencia pacotes Flatpak nesta versão.

## Desenvolvimento

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src
```

Para experimentar localmente é preciso instalar `python3-pyqt6` e `python3-apt`. Exemplo usando o Python fornecido pela distribuição:

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos.gui
```

O ponto de entrada correto para execução direta a partir do checkout é:

```bash
PYTHONPATH=src /usr/bin/python3 -c 'from mainuan_recursos.gui import main; raise SystemExit(main())'
```

### Gerar .deb (sem sudo)

```bash
bash build-package.sh
```

O pacote independente de arquitetura aparece em `dist/mainuan-atualizador-recursos_0.1.0_all.deb`. Em pushes e PRs, o GitHub Actions envia o `.deb` como artefato. Ao publicar uma tag `v*`, o workflow também deve anexá-lo à Release.

**Não instalar o atualizador original do TigerOS em máquinas Mainuan.** A extração indiscriminada de TAR como root foi intencionalmente removida. O catálogo e a entrega de novos recursos devem ocorrer como pacotes Debian assinados via APT.
