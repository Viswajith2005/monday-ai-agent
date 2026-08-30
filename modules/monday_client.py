import time
import json
import logging
import requests
from config import Config

logger = logging.getLogger(__name__)

class MondayClient:
    def __init__(self, api_token: str = None):
        self.api_token = api_token or Config.MONDAY_API_TOKEN
        self.api_url = Config.MONDAY_API_URL
        self.headers = {
            "Authorization": self.api_token,
            "Content-Type": "application/json",
            "API-Version": "2024-01"
        }
        self._cache = {}
        self._cache_ts = {}

    def _execute_query(self, query: str, variables: dict = None, retries: int = 6):
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        for attempt in range(retries):
            try:
                resp = requests.post(self.api_url, json=payload, headers=self.headers, timeout=40)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", 6)) + 2
                    logger.warning(f"Monday API rate limit 429. Sleeping {retry_after}s...")
                    time.sleep(retry_after)
                    continue
                if resp.status_code != 200:
                    logger.error(f"Monday API Error {resp.status_code}: {resp.text}")
                    time.sleep(3)
                    continue

                data = resp.json()
                if "errors" in data:
                    err_msg = data["errors"][0].get("message", "")
                    if "complexity" in err_msg.lower() or "limit" in err_msg.lower():
                        time.sleep(4)
                        continue
                    raise Exception(f"Monday GraphQL Error: {data['errors']}")
                return data.get("data", {})
            except requests.exceptions.RequestException as e:
                logger.warning(f"Request failed attempt {attempt+1}: {e}")
                time.sleep(3)

        raise Exception("Failed to execute Monday API query after multiple retries.")

    def list_all_boards(self):
        query = """
        query {
            boards (limit: 50) {
                id
                name
                state
                columns {
                    id
                    title
                    type
                }
            }
        }
        """
        data = self._execute_query(query)
        return data.get("boards", [])

    def discover_board_ids(self):
        deals_id = Config.MONDAY_DEALS_BOARD_ID
        wo_id = Config.MONDAY_WORK_ORDERS_BOARD_ID

        if deals_id and wo_id:
            return {"deals_board_id": deals_id, "work_orders_board_id": wo_id}

        boards = self.list_all_boards()
        for b in boards:
            b_name = b["name"].lower()
            if not deals_id and ("deal" in b_name or "funnel" in b_name or "pipeline" in b_name):
                deals_id = b["id"]
            if not wo_id and ("work_order" in b_name or "work order" in b_name or "tracker" in b_name or "operations" in b_name):
                wo_id = b["id"]

        return {"deals_board_id": deals_id, "work_orders_board_id": wo_id}

    def fetch_board_items(self, board_id: str, force_refresh: bool = False):
        board_id = str(board_id)
        now = time.time()
        
        if not force_refresh and board_id in self._cache:
            if (now - self._cache_ts.get(board_id, 0)) < Config.CACHE_TTL_SECONDS:
                return self._cache[board_id]

        logger.info(f"Fetching live items from Monday board {board_id}...")

        initial_query = """
        query ($boardId: [ID!]) {
            boards (ids: $boardId) {
                id
                name
                columns {
                    id
                    title
                    type
                }
                items_page (limit: 100) {
                    cursor
                    items {
                        id
                        name
                        created_at
                        column_values {
                            id
                            text
                            value
                            type
                        }
                    }
                }
            }
        }
        """
        res = self._execute_query(initial_query, {"boardId": [board_id]})
        boards = res.get("boards", [])
        if not boards:
            raise ValueError(f"Board with ID {board_id} not found in Monday.com account.")

        board_obj = boards[0]
        board_name = board_obj["name"]
        columns = board_obj["columns"]
        col_id_to_title = {c["id"]: c["title"] for c in columns}

        items_page = board_obj.get("items_page", {})
        all_raw_items = items_page.get("items", [])
        cursor = items_page.get("cursor")

        page_query = """
        query ($cursor: String!) {
            next_items_page (limit: 100, cursor: $cursor) {
                cursor
                items {
                    id
                    name
                    created_at
                    column_values {
                        id
                        text
                        value
                        type
                    }
                }
            }
        }
        """

        while cursor:
            time.sleep(0.3)
            next_res = self._execute_query(page_query, {"cursor": cursor})
            next_page = next_res.get("next_items_page", {})
            new_items = next_page.get("items", [])
            all_raw_items.extend(new_items)
            cursor = next_page.get("cursor")
            if not new_items or not cursor:
                break

        parsed_records = []
        for item in all_raw_items:
            rec = {
                "item_id": item["id"],
                "item_name": item["name"],
                "created_at": item.get("created_at")
            }
            for cv in item.get("column_values", []):
                col_title = col_id_to_title.get(cv["id"], cv["id"])
                text_val = cv.get("text")
                raw_val = cv.get("value")
                
                if (text_val is None or text_val == "") and raw_val:
                    try:
                        parsed_json = json.loads(raw_val)
                        if isinstance(parsed_json, dict):
                            if "date" in parsed_json:
                                text_val = parsed_json["date"]
                            elif "label" in parsed_json:
                                text_val = parsed_json["label"]
                            elif "text" in parsed_json:
                                text_val = parsed_json["text"]
                    except Exception:
                        pass
                        
                rec[col_title] = text_val

            parsed_records.append(rec)

        result = {
            "board_id": board_id,
            "board_name": board_name,
            "columns": columns,
            "total_items": len(parsed_records),
            "records": parsed_records,
            "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        self._cache[board_id] = result
        self._cache_ts[board_id] = now
        return result
