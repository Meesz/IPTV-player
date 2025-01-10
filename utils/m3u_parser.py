import re
import logging
from models.playlist import Channel, Playlist

logger = logging.getLogger(__name__)

class M3UParser:
    @staticmethod
    def parse(file_path: str) -> Playlist:
        logger.debug(f"Starting to parse M3U file: {file_path}")
        playlist = Playlist()
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                logger.debug("Reading M3U file contents")
                lines = f.readlines()
                
            logger.debug(f"Read {len(lines)} lines from file")
            
            if not lines:
                logger.error("File is empty")
                raise ValueError("Empty M3U file")
                
            if not lines[0].strip().startswith('#EXTM3U'):
                logger.error("File doesn't start with #EXTM3U")
                raise ValueError("Invalid M3U file format")
                
            current_channel = None
            channels_count = 0
            
            for line_num, line in enumerate(lines[1:], 1):
                line = line.strip()
                if not line:
                    continue
                    
                if line.startswith('#EXTINF'):
                    logger.debug(f"Processing EXTINF line {line_num}: {line[:100]}...")
                    info_regex = r'#EXTINF:-1(?:.*tvg-id="(.*?)")?(?:.*tvg-name="(.*?)")?(?:.*group-title="(.*?)")?(?:.*tvg-logo="(.*?)")?,(.+)$'
                    match = re.match(info_regex, line)
                    
                    if match:
                        epg_id = match.group(1) or ""
                        name = match.group(2) or match.group(5)
                        group = match.group(3) or ""
                        logo = match.group(4) or ""
                        current_channel = (name, group, logo, epg_id)
                        logger.debug(f"Found channel info: name={name}, group={group}")
                
                elif not line.startswith('#') and current_channel:
                    logger.debug(f"Processing URL line {line_num}: {line[:100]}...")
                    name, group, logo, epg_id = current_channel
                    channel = Channel(
                        name=name,
                        url=line,
                        group=group,
                        logo=logo,
                        epg_id=epg_id
                    )
                    playlist.add_channel(channel)
                    channels_count += 1
                    current_channel = None
            
            logger.info(f"Successfully parsed {channels_count} channels")
            return playlist
            
        except Exception as e:
            logger.error(f"Error parsing M3U file: {str(e)}", exc_info=True)
            raise 