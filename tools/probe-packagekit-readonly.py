#!/usr/bin/python3
"""Resolve e SIMULATE no daemon real; bloqueia qualquer pedido mutante."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PyQt6.QtCore import QCoreApplication, QTimer
from PyQt6 import QtDBus
from mainuan_recursos.packagekit import Transaction, Transport, SERVICE, ROOT, PROPERTIES, SIMULATE
from mainuan_recursos.packages import identity, validate_effects


class ReadOnlyTransport(Transport):
    def call(self,path,interface,method,args,callback):
        if method=='InstallPackages':
            if not args[0] & SIMULATE:
                raise RuntimeError('Pedido real de instalação bloqueado pelo ensaio.')
        elif method not in ('CreateTransaction','SetHints','Resolve','GetAll'):
            raise RuntimeError('Método fora do escopo de leitura/simulação.')
        super().call(path,interface,method,args,callback)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    opts=parser.parse_args()
    import apt
    cache=apt.Cache()
    choice=next((name for name in ('hello','tree') if name in cache and not cache[name].is_installed
                 and cache[name].candidate and any(o.trusted and o.origin=='Ubuntu' for o in cache[name].candidate.origins)),None)
    app=QCoreApplication([])
    report={'real_installation_requests':0,'password_prompts':0,'simulation_only':True,'selected_package':choice,'installed_before':False if choice else None}
    bus=QtDBus.QDBusConnection.systemBus()
    def query(interface,method,args):
        message=QtDBus.QDBusMessage.createMethodCall(SERVICE,ROOT,interface,method)
        message.setInteractiveAuthorizationAllowed(False)
        message.setArguments(args)
        reply=bus.call(message,QtDBus.QDBus.CallMode.Block,3000)
        return reply.arguments() if reply.type()!=QtDBus.QDBusMessage.MessageType.ErrorMessage else {'error':reply.errorName()}
    report['can_authorize_install']=query(SERVICE,'CanAuthorize',['org.freedesktop.packagekit.package-install'])
    properties=query(PROPERTIES,'GetAll',[SERVICE])
    report['packagekit_locked']=properties[0].get('Locked') if isinstance(properties,list) and properties and isinstance(properties[0],dict) else None
    report['active_transactions']=query(SERVICE,'GetTransactionList',[])
    # Objetos QDBusObjectPath não são serializáveis diretamente.
    def default(value):
        return value.path() if hasattr(value,'path') else str(value)
    transactions=[]
    progress=[]
    def start(method,values,callback,simulate=False):
        transaction=Transaction(transport_factory=ReadOnlyTransport)
        transactions.append(transaction)
        transaction.progress.connect(lambda text,percent:progress.append([text,percent]))
        transaction.finished.connect(callback)
        transaction.start(method,values,simulate=simulate)
    def finish():
        if choice:
            report['installed_after']=apt.Cache()[choice].is_installed
        report['progress']=progress
        opts.output.parent.mkdir(parents=True,exist_ok=True)
        opts.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=default))
        print(json.dumps(report,ensure_ascii=False,default=default))
        app.quit()
    def failure_probe(result):
        report['missing_package_error']={'success':result.success,'error':result.error}
        finish()
    def simulated(result):
        report['simulation']={'success':result.success,'error':result.error,'effects':result.packages}
        if result.success:
            try:
                report['validated_effects']=validate_effects(result.packages,(expected,),cache)
            except Exception as exc:
                report['validation_error']=str(exc)
        # Falha real do daemon em transação simulada, sem solicitar instalação.
        start('InstallPackages',['mainuan-homologacao-inexistente;1.0;all;repo-inexistente'],failure_probe,simulate=True)
    def resolved(result):
        report['resolve']={'success':result.success,'error':result.error,'packages':result.packages}
        found=next((package_id for info,package_id in result.packages if info==2 and identity(package_id)==expected),None)
        if result.success and found:
            start('InstallPackages',[found],simulated,simulate=True)
        else:
            finish()
    if not choice:
        report['skipped']='Nenhum pacote inofensivo elegível disponível para simulação.'
        finish()
        return 0
    candidate=cache[choice].candidate
    expected=(choice,candidate.version,candidate.architecture)
    start('Resolve',[choice],resolved)
    QTimer.singleShot(30000,app.quit)
    app.exec()
    return 0 if report.get('simulation',{}).get('success') and report.get('validated_effects') and not report.get('missing_package_error',{}).get('success',True) else 1


if __name__=='__main__':
    raise SystemExit(main())
