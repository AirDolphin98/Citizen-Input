
import openai
import gspread
import pandas
from oauth2client.service_account import ServiceAccountCredentials
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv

# === CONFIG ===
load_dotenv()
openai_client = openai.OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)
GOOGLE_CREDENTIALS_FILE = 'citizen-input-89e393467ee6.json'
SHEET_NAME = 'Opinions Spreadsheet'
DOC_ID = '1WFngQxjim2M7geC30rGb5ft4H1pEavQ_IoSl9IWLt-s'  # 🔁 Use your own doc ID here
MODEL = 'gpt-4o'
# ===============

# === Setup Google APIs ===
scope = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/drive',
    'https://spreadsheets.google.com/feeds',
]
creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDENTIALS_FILE, scope)

# Google Sheets
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).get_worksheet_by_id(558979275)
df = pandas.DataFrame(sheet.get_all_records())

# Google Docs
docs_service = build('docs', 'v1', credentials=creds)

def get_document_end_index(doc_id):
    doc = docs_service.documents().get(documentId=doc_id).execute()
    return doc['body']['content'][-1]['endIndex'] - 1

def append_text(doc_id, text):
    """Appends text to the end of an existing Google Doc"""
    index = get_document_end_index(doc_id)
    requests = [
        {
            "insertText": {
                "location": {"index": index},
                "text": text
            }
        }
    ]
    docs_service.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

# === 1. Get Opinions ===
opinions = df['Opinion'].dropna().tolist()
opinion_text = "\n".join(f"- {op}" for op in opinions)

# === 2. Grouping prompt (Japanese) ===
grouping_prompt = f"""
以下は日本の市民から集めた政治的な意見です。類似する意見をテーマごとに分類してください。

各テーマについて以下の情報を出力してください：
1. テーマのタイトル（簡潔に）
2. テーマの概要（どんな問題意識か）
3. 含まれる意見（リスト形式）

市民の意見一覧：
{opinion_text}
"""

grouping_response = openai_client.responses.create(
    model=MODEL,
    instructions="あなたは市民の声を分類・要約する政策アナリストです。",
    input=grouping_prompt
)

grouped_output = grouping_response.output_text
group_blocks = grouped_output.split("\n\n")

# === 3. Append header (optional) ===
header = "\n\n---\n📝 **新しい市民提案のまとめ**\n\n"
append_text(DOC_ID, header)

# === 4. Draft and append each policy proposal ===
for i, group in enumerate(group_blocks):
    if not group.strip():
        continue

    policy_prompt = f"""
以下の市民の意見グループに基づいて、日本の行政向けの政策提案書を作成してください。

内容：
{group}

フォーマット：
1. 政策分野（タイトル）
2. 問題提起（なぜこの問題が重要か）
3. 政策提案（具体的にどうするか）
4. 正当性・期待される効果（理由）

日本語で簡潔かつ明瞭に記述してください。
"""

    proposal_response = openai_client.responses.create(
        model=MODEL,
        instructions="あなたは日本の政策立案を支援するAIアシスタントです。",
        input=policy_prompt
    )

    policy_text = proposal_response.output_text

    section_header = f"\n\n📌 テーマ {i+1}\n{group}\n\n📄 政策提案:\n"
    formatted_section = section_header + policy_text + "\n"
    append_text(DOC_ID, formatted_section)

print(f"\n✅ 既存ドキュメントに追加完了！\nhttps://docs.google.com/document/d/{DOC_ID}/edit")
