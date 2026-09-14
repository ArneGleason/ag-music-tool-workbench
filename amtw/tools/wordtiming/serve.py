"""Serve audition files with byte ranges; bare http.server cannot seek WAVs reliably."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        self.byte_range = None
        path = Path(self.translate_path(self.path)).resolve()
        root = Path(self.directory).resolve()
        if not path.is_relative_to(root):
            self.send_error(403); return None
        value = self.headers.get('Range')
        if not value or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', value)
        if not match or not any(match.groups()):
            self.send_error(416); return None
        a,b = match.groups()
        start = int(a) if a else max(0,size-int(b))
        end = min(int(b),size-1) if b and a else size-1
        if start > end or start >= size:
            self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return None
        f=path.open('rb');f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type',self.guess_type(str(path)))
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.send_header('Last-Modified',self.date_time_string(path.stat().st_mtime))
        self.end_headers();self.byte_range=(start,end)
        return f

    def end_headers(self):
        self.send_header('Accept-Ranges','bytes')
        super().end_headers()

    def copyfile(self,source,output):
        try:
            if self.byte_range is None:
                return super().copyfile(source,output)
            remaining=self.byte_range[1]-self.byte_range[0]+1
            while remaining:
                block=source.read(min(65536,remaining))
                if not block:break
                output.write(block);remaining-=len(block)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):
            pass  # switching a phrase legitimately cancels an earlier range


def serve(directory,port=8741):
    root=Path(directory).resolve()
    if not root.is_dir():raise ValueError('Review directory does not exist')
    print(f'Word timing review: http://127.0.0.1:{port}/',flush=True)
    ThreadingHTTPServer(('127.0.0.1',port),partial(RangeHandler,directory=str(root))).serve_forever()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('directory');p.add_argument('--port',type=int,default=8741)
    a=p.parse_args();serve(a.directory,a.port)
