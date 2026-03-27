
import re
import copy
import json


def write_event(helper, ew, data, event_timestamp, sourcetype):
   cnt = 0
   event = helper.new_event(
      index=helper.get_output_index(),
      sourcetype=sourcetype,
      data=json.dumps(data),
      time=event_timestamp,
   )
   ew.write_event(event)
   cnt += 1
   return cnt


def write_AAR_event(helper, ew, data):
   """
   Flattenthe the nested AAR event & Extracted the channelInfo.activities.nodes.startTime as Ingestion Time
   It iterates through the channelInfo array and the nested activities.nodes list. 
   For every individual node, it creates a new object where the nodes list is replaced by a single-item list containing only that specific node.
   """
   # Extract top-level agent information
   agent_info = {k: v for k, v in data.items() if k != "channelInfo"}   
   # Iterate through each channelInfo
   cnt = 0
   for channel in data.get("channelInfo", []):     
      # Create a copy of channel info excluding the activities/nodes
      channel_base = {k: v for k, v in channel.items() if k != "activities"}     
      # Access the nodes list
      nodes = channel.get("activities", {}).get("nodes", [])   
      for node in nodes:
         # Create a new object for each node
         new_obj = copy.deepcopy(agent_info)
         new_obj["channelInfo"] = copy.deepcopy(channel_base)        
         # Insert the node information back
         new_obj["channelInfo"]["activity"] = {"node": node}        
         # Extract startTime as ingestion time (convert millisecond to second)
         event_timestamp = node.get("startTime") / 1000.0
         write_event(helper, ew, new_obj, event_timestamp, "cisco:webex:contact:center:AAR")
         cnt += 1
   return cnt


def write_CAR_event(helper, ew, data):
   """
   Flattenthe the nested CAR event & Extracted the activities.nodes.createdTime as Ingestion Time
   It iterates through the activities.nodes list. 
   For every individual node, it creates a new object where the nodes list is replaced by a single-item list containing only that specific node.
   """
   # Extract top-level agent information
   info = {k: v for k, v in data.items() if k != "activities"} 
   # Iterate through each activiy
   cnt = 0
   # Access the nodes list
   nodes = data.get("activities", {}).get("nodes", [])
   # print(f"[-] nodes: {nodes}")
   for node in nodes:
      # Create a new object for each node
      new_obj = copy.deepcopy(info)         
      # Insert the node information back
      new_obj["activity"] = {"node": node} 
      # Extract createdTime as ingestion time (convert millisecond to second)
      event_timestamp = node.get("createdTime") / 1000.0
      write_event(helper, ew, new_obj, event_timestamp, "cisco:webex:contact:center:CAR")
      cnt += 1
   return cnt


def extract_nested_list(response):
   data_content = response.get("data", {})
   first_level_val = next(iter(data_content.values()), {})
   events = next(iter(first_level_val.values()), [])
   return events


def prepare_paginated_query(query_str):
    # Remove any existing hardcoded pagination blocks to start fresh
    query_str = re.sub(r",?\s*pagination\s*:\s*\{[^}]+\}", "", query_str)

    # Update the Query Header (Variable Definitions)
    # Adds "$cursor: String" inside the query(...) parentheses
    if "$cursor" not in query_str:
        query_str = re.sub(
            r"query\s*\(([^)]+)\)",
            r"query (\1, $cursor: String)",
            query_str
        )

    # Update the Data Object (Arguments) with "pagination: { cursor: $cursor })"
    if "pagination" not in query_str:
        query_str = re.sub(
            r"(\b(?!query\b)\w+\s*\([^)]+)\)",
            r"\1, pagination: { cursor: $cursor })",
            query_str
        )

    # Universal PageInfo Injection
    if "pageInfo" not in query_str:
        # Matches the main object and the first inner list block
        query_str = re.sub(
            r"(\w+\s*\{)(\s*\w+\s*\{[^{}]*\})",
            r"\1\2\n    pageInfo {\n      hasNextPage\n      endCursor\n    }",
            query_str
        )

    # Final Cleanup: Fix double commas or spaces caused by regex
    query_str = query_str.replace(", ,", ",").replace("(,", "(").strip()

    return query_str


def find_key_recursive(obj, target_key):
   """
   Recursively searches for a key in a nested dictionary/list structure.
   Returns the value of the key if found, otherwise returns None.
   """
   if isinstance(obj, dict):
      #Check if the key is at the current level
      if target_key in obj:
         return obj[target_key]
      #If not, drill down into each value
      for value in obj.values():
         result = find_key_recursive(value, target_key)
         if result is not None:
               return result
   elif isinstance(obj, list):
      #If it"s a list, check each item in the list
      for item in obj:
         result = find_key_recursive(item, target_key)
         if result is not None:
               return result
   return None