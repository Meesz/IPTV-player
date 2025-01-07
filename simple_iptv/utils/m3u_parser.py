import re
from models.playlist import Channel, Playlist

class M3UParser:
    @staticmethod
    def parse(file_path: str) -> Playlist:
        playlist = Playlist()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        if not lines[0].strip().startswith('#EXTM3U'):
            raise ValueError("Invalid M3U file format")
            
        current_channel = None
        
        for line in lines[1:]:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith('#EXTINF'):
                info_regex = r'#EXTINF:-1(?:.*tvg-name="(.*?)")?(?:.*group-title="(.*?)")?(?:.*tvg-logo="(.*?)")?,(.+)$'
                match = re.match(info_regex, line)
                
                if match:
                    name = match.group(1) or match.group(4)
                    group = match.group(2) or ""
                    logo = match.group(3) or ""
                    current_channel = (name, group, logo)
            
            elif not line.startswith('#') and current_channel:
                name, group, logo = current_channel
                channel = Channel(name=name, url=line, group=group, logo=logo)
                playlist.add_channel(channel)
                current_channel = None
                
        return playlist 