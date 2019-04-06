import json
import os
import shutil
from multiprocessing import Process, Value
from queue import Queue, Empty, Full
from threading import Thread

from apscheduler.schedulers.background import BackgroundScheduler

import config
from indexer import Indexer
from parsing import GenericFileParser, Md5CheckSumCalculator, ExtensionMimeGuesser, MediaFileParser, TextFileParser, \
    PictureFileParser, Sha1CheckSumCalculator, Sha256CheckSumCalculator, ContentMimeGuesser, MimeGuesser, FontParser, \
    PdfFileParser, DocxParser, EbookParser
from search import Search
from storage import Directory
from storage import Task, LocalStorage
from thumbnail import ThumbnailGenerator


class RunningTask:

    def __init__(self, task: Task):
        self.total_files = Value("i", 0)
        self.parsed_files = Value("i", 0)
        self.task = task
        self.done = Value("i", 0)

    def to_json(self):
        return json.dumps({"parsed": self.parsed_files.value, "total": self.total_files.value, "id": self.task.id})


class Crawler:

    def __init__(self, enabled_parsers: list, mime_guesser: MimeGuesser = ExtensionMimeGuesser(), indexer=None,
                 dir_id=0,
                 root_dir="/"):
        self.documents = []
        self.enabled_parsers = enabled_parsers
        self.indexer = indexer
        self.dir_id = dir_id
        self.root_dir = root_dir

        for parser in self.enabled_parsers:
            if parser.is_default:
                self.default_parser = parser

        self.ext_map = {}

        for parser in self.enabled_parsers:
            for ext in parser.mime_types:
                self.ext_map[ext] = parser

        self.mime_guesser = mime_guesser

    def crawl(self, root_dir: str, counter: Value = None, total_files = None):

        in_q = Queue(50000)  # TODO: get from config?
        out_q = Queue()

        threads = []
        print("Creating %d threads" % (config.parse_threads,))
        for _ in range(config.parse_threads):
            t = Thread(target=self.parse_file, args=[in_q, out_q, ])
            threads.append(t)
            t.start()

        indexer_thread = Thread(target=self.index_file, args=[out_q, counter, ])
        indexer_thread.start()

        for root, dirs, files in os.walk(root_dir):
            for filename in files:
                while True:
                    try:
                        in_q.put(os.path.join(root, filename), timeout=10)
                        if total_files:
                            total_files.value += 1
                        break
                    except Full:
                        continue

        in_q.join()
        out_q.join()

        for _ in threads:
            in_q.put(None)
        out_q.put(None)

        indexer_thread.join()
        for t in threads:
            t.join()

    def countFiles(self, root_dir: str):
        count = 0

        for root, dirs, files in os.walk(root_dir):
            count += len(files)

        return count

    def parse_file(self, in_q: Queue, out_q: Queue):

        while True:
            try:
                full_path = in_q.get(timeout=1)
                if full_path is None:
                    break
            except Empty:
                break

            try:
                mime = self.mime_guesser.guess_mime(full_path)
                parser = self.ext_map.get(mime, self.default_parser)

                doc = parser.parse(full_path)
                doc["mime"] = mime
                out_q.put(doc)
            except:
                pass
            finally:
                in_q.task_done()

    def index_file(self, out_q: Queue, count: Value):

        if self.indexer is None:
            while True:
                try:
                    doc = out_q.get(timeout=120)
                    if doc is None:
                        break
                except Empty:
                    break
                self.documents.append(doc)
                out_q.task_done()
            return

        while True:
            try:
                doc = out_q.get(timeout=600)
                if doc is None:
                    break
            except Empty:
                print("outq empty")
                break

            try:
                self.documents.append(doc)
                count.value += 1

                if count.value % config.index_every == 0:
                    self.indexer.index(self.documents, self.dir_id)
                    self.documents.clear()
            except:
                pass
            finally:
                out_q.task_done()
        self.indexer.index(self.documents, self.dir_id)


class TaskManager:
    def __init__(self, storage: LocalStorage):
        self.current_task = None
        self.storage = storage
        self.current_process = None
        self.indexer = Indexer("changeme")

        scheduler = BackgroundScheduler()
        scheduler.add_job(self.check_new_task, "interval", seconds=0.5)
        scheduler.start()

    def start_task(self, task: Task):
        self.current_task = RunningTask(task)

        directory = self.storage.dirs()[task.dir_id]

        if task.type == Task.INDEX:
            self.current_process = Process(target=self.execute_crawl, args=(directory,
                                                                            self.current_task.parsed_files,
                                                                            self.current_task.done,
                                                                            self.current_task.total_files))

        elif task.type == Task.GEN_THUMBNAIL:
            self.current_process = Process(target=self.execute_thumbnails, args=(directory,
                                                                                 self.current_task.total_files,
                                                                                 self.current_task.parsed_files,
                                                                                 self.current_task.done))
        self.current_process.start()

    def execute_crawl(self, directory: Directory, counter: Value, done: Value, total_files: Value):

        Search("changeme").delete_directory(directory.id)

        chksum_calcs = []

        for arg in directory.get_option("CheckSumCalculators").split(","):

            if arg.strip() == "md5":
                chksum_calcs.append(Md5CheckSumCalculator())
            elif arg.strip() == "sha1":
                chksum_calcs.append(Sha1CheckSumCalculator())
            elif arg.strip() == "sha256":
                chksum_calcs.append(Sha256CheckSumCalculator())

        mime_guesser = ExtensionMimeGuesser() if directory.get_option("MimeGuesser") == "extension" \
            else ContentMimeGuesser()

        c = Crawler([GenericFileParser(chksum_calcs, directory.path),
                     MediaFileParser(chksum_calcs, directory.path),
                     TextFileParser(chksum_calcs, int(directory.get_option("TextFileContentLength")), directory.path),
                     PictureFileParser(chksum_calcs, directory.path),
                     FontParser(chksum_calcs, directory.path),
                     PdfFileParser(chksum_calcs, int(directory.get_option("PdfFileContentLength")), directory.path),
                     DocxParser(chksum_calcs, int(directory.get_option("SpreadsheetContentLength")), directory.path),
                     EbookParser(chksum_calcs, int(directory.get_option("EbookContentLength")), directory.path)],
                    mime_guesser, self.indexer, directory.id)
        c.crawl(directory.path, counter, total_files)

        done.value = 1

    def execute_thumbnails(self, directory: Directory, total_files: Value, counter: Value, done: Value):

        dest_path = os.path.join("static/thumbnails", str(directory.id))
        if os.path.exists(dest_path):
            shutil.rmtree(dest_path)

        docs = Search("changeme").get_all_documents(directory.id)

        tn_generator = ThumbnailGenerator(int(directory.get_option("ThumbnailSize")),
                                          int(directory.get_option("ThumbnailQuality")),
                                          directory.get_option("ThumbnailColor"))
        tn_generator.generate_all(docs, dest_path, counter, directory, total_files)

        done.value = 1

    def cancel_task(self):
        self.current_task.done.value = 1

    def check_new_task(self):

        if self.current_task is None:
            tasks = self.storage.tasks()
            if len(tasks) > 0:
                self.start_task(tasks[sorted(tasks)[0]])
        else:
            if self.current_task.done.value == 1:
                self.current_process.terminate()
                self.storage.del_task(self.current_task.task.id)
                self.current_task = None
