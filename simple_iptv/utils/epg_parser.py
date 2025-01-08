import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict
from models.epg import Program, EPGData, EPGGuide

class EPGParser:
    @staticmethod
    def parse_date(date_str: str) -> datetime:
        """Parse various EPG date formats"""
        # Remove timezone if present (we'll assume UTC)
        date_str = date_str.split('+')[0].split('-')[0]
        
        # Remove any spaces or 'T'
        date_str = date_str.replace(' ', '').replace('T', '')
        
        # Parse YYYYMMDDHHMMSS format
        try:
            return datetime.strptime(date_str, '%Y%m%d%H%M%S')
        except ValueError:
            # Try YYYYMMDDHHMM format
            try:
                return datetime.strptime(date_str, '%Y%m%d%H%M')
            except ValueError:
                raise ValueError(f"Unsupported date format: {date_str}")
    
    @staticmethod
    def parse_xmltv(file_path: str) -> EPGGuide:
        guide = EPGGuide()
        channel_count = 0
        program_count = 0
        
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            for program in root.findall('.//programme'):
                channel_id = program.get('channel')
                if not channel_id:
                    continue
                
                # Parse program data with new date parser
                try:
                    start_time = EPGParser.parse_date(program.get('start', ''))
                    end_time = EPGParser.parse_date(program.get('stop', ''))
                except ValueError as e:
                    print(f"Warning: Skipping program due to invalid date: {e}")
                    continue
                
                title = program.find('title')
                title_text = title.text if title is not None else "No Title"
                
                desc = program.find('desc')
                desc_text = desc.text if desc is not None else ""
                
                category = program.find('category')
                category_text = category.text if category is not None else ""
                
                prog = Program(
                    title=title_text,
                    start_time=start_time,
                    end_time=end_time,
                    description=desc_text,
                    category=category_text
                )
                
                # Add to guide
                channel_data = guide.get_channel_data(channel_id)
                if channel_data is None:
                    channel_data = EPGData(channel_id=channel_id, programs=[])
                    guide.add_channel_data(channel_id, channel_data)
                    channel_count += 1
                
                channel_data.programs.append(prog)
                program_count += 1
            
            print(f"EPG loaded: {channel_count} channels, {program_count} programs")
            
            # Debug: Print some channel IDs
            channel_ids = list(guide._data.keys())[:5]
            print(f"Sample channel IDs: {channel_ids}")
            
            return guide
            
        except Exception as e:
            raise ValueError(f"Failed to parse EPG file: {str(e)}") 