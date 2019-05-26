# Do not change option names
default_options = {
    "ThumbnailQuality": "85",
    "ThumbnailSize": "272",
    "ThumbnailColor": "FF00FF",
    "TextFileContentLength": "2000",
    "PdfFileContentLength": "2000",
    "DocxContentLength": "2000",
    "SpreadSheetContentLength": "2000",
    "EbookContentLength": "2000",
    "MimeGuesser": "extension",  # extension, content
    "CheckSumCalculators": "",  # md5, sha1, sha256
    "FileParsers": "media, text, picture, font, pdf, docx, spreadsheet, ebook"
}

# Index documents after every X parsed files (Larger number will use more memory)
index_every = 10000

# See https://www.elastic.co/guide/en/elasticsearch/reference/current/analysis-ngram-tokenizer.html#_configuration_16
nGramMin = 3
nGramMax = 3
elasticsearch_url = "http://localhost:9200"
elasticsearch_index = "sist"

# Password hashing
bcrypt_rounds = 13
# sqlite3 database path
db_path = "./local_storage.db"

# Set to true to allow guests to search any directory
allow_guests = True

# Number of threads used for parsing
parse_threads = 32

# Number of threads used for thumbnail generation
tn_threads = 32


try:
    import cairosvg
    cairosvg = True
except:
    cairosvg = False

VERSION = "1.2a"
