"""Edit a mixed plot, diagram and native-3D composition in a local browser."""
import argparse
import threading
from composition_recipes import make_reports
from inklet.experimental.layout_editor import LayoutEditor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=0,help='Local port; 0 chooses an available port')
    args=parser.parse_args()
    reports,_=make_reports()
    reports[0]['chart'].annotate(2,3,'Reference observation',key='observation',side='s',clear=4)
    with LayoutEditor(reports[0],preset='scientific.general').start(port=args.port) as editor:
        print(f'Open {editor.url} — press Ctrl+C to stop.',flush=True)
        try:threading.Event().wait()
        except KeyboardInterrupt:pass


if __name__=='__main__':main()
