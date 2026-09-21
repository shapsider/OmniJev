"""Read selected public ZIP members via verified HTTP byte ranges."""
import io
import urllib.request
import zipfile


class RemoteFile(io.RawIOBase):
    def __init__(self,url,size):
        self.url=url
        self.size=size
        self.pos=0
        self.downloaded=0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        if self.pos<0:raise ValueError('Negative seek')
        return self.pos

    def read(self,n=-1):
        n=min(self.size-self.pos,n if n>=0 else self.size-self.pos)
        if n<=0:return b''
        start=self.pos
        end=start+n-1
        # Query makes intermediary caches distinguish ranges.
        url=self.url+('&' if '?' in self.url else '?')+f'byte_range={start}-{end}'
        req=urllib.request.Request(url,headers={'Range':f'bytes={start}-{end}'})
        with urllib.request.urlopen(req,timeout=120) as response:
            expected=f'bytes {start}-{end}/{self.size}'
            if response.status!=206 or response.headers.get('Content-Range')!=expected:
                raise IOError(f'Range not honored: {response.status} {response.headers.get("Content-Range")} expected {expected}')
            data=response.read(n+1)
        if len(data)!=n:raise IOError(f'Range length mismatch: {len(data)} != {n}')
        self.pos+=n
        self.downloaded+=n
        return data


def open_zip(url,size):
    return zipfile.ZipFile(RemoteFile(url,size))


if __name__=='__main__':
    import sys
    z=open_zip(sys.argv[1],int(sys.argv[2]))
    for info in z.infolist()[:20]:print(info.filename,info.file_size,info.compress_size)
    print('Members',len(z.infolist()))
