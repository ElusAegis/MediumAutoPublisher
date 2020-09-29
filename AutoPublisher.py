from medium import Client
from medium import MediumError
import sys
import os
import copy

ACCOUNT_INFO = "accountsInfo.txt"
SUBMIT_TEXT_FILE = "submitText.txt"
PATH = ""
IMAGES_PATH = "images/"


class Account:

    def __init__(self, account_str=None, language=None, token=None, name=None):

        self.client = None
        self.user = None

        self.language = language
        self.token = token
        self.name = name

        if account_str != None:
            splitted_account_str = account_str.rstrip().replace(" ", "").split(",")
            if (len(splitted_account_str) != 3):
                raise AccountWarning(account_str)
            else:
                self.name, self.language, self.token = splitted_account_str

        self.articles = None

    def __str__(self):
        return "{Name: %s, Language: %s, Token: %s, ArticleCount: %d}" %\
               (self.name, self.language, self.token, len(self.articles) if self.articles is not None else 0)

    def __repr__(self):
        return "{Name: %s, Language: %s, Token: %s, ArticleCount: %d}" %\
               (self.name, self.language, self.token, len(self.articles) if self.articles is not None else 0)

class AccountWarning(Warning):

    def __init__(self, account_str):

        print("Incorrect format for account info: %s" % account_str, file=sys.stderr)


class Article:
    def __init__(self, raw_text):

        self.content = None
        self.images = []

        allowed_format = {"jpeg", "png", "gif", "tiff"}


        title = False
        language = False
        self.text = []
        for text_line in raw_text:
            if not language:
                if text_line == "\n":
                    continue
                preped_line = text_line.replace(" ", "").split(":")
                if preped_line[0] == "Language" and len(preped_line) == 2:
                    self.language = preped_line[1]
                    language = True
                else:
                    raise ArticleWarning(title, language, text_line)
            elif not title:
                if text_line == "\n":
                    continue
                preped_line = text_line.replace(" ", "").split(":")
                if preped_line[0] == "Title" and len(preped_line) > 1 and (preped_line[1] != '' or len(preped_line) > 2):
                    index = text_line.find(":")
                    self.title = text_line[index + 1: ]
                    title = True
                else:
                    raise ArticleWarning(title, language, text_line)
            else:
                preped_line = text_line.replace(" ", "").split(":")
                if preped_line[0] == "IMAGE" and len(preped_line) >= 2:
                    format_split = preped_line[-1].split(".")
                    if len(format_split) < 2 or format_split[-1] not in allowed_format:
                        raise ImageWarning(format_split[-1])
                    self.images += ["".join(preped_line[1:])]
                self.text += [text_line]

        if not self.text:
            raise ArticleWarning(title, language)


    def __str__(self):
        return "{Language: %s, Title: %s, Text: %s}" % (self.language, self.title, self.text)

    def __repr__(self):
        return "{Language: %s, Title: %s, Text: %s}" % (self.language, self.title, self.text)

class ArticleWarning(Warning):

    def __init__(self, title, language, line=None):
        if not language:
            print("Found an inappropriate line instead of 'Language' specification : %s" % line, file=sys.stderr)
        elif not title:
            print("Found an inappropriate line instead of 'Title' specification : %s" % line, file=sys.stderr)
        else:
            print("Creating an article with empty body", file=sys.stderr)

class ImageWarning(Warning):
    def __init__(self, format):
        print("Incorrect format '%s'. Only {jpeg, png, gif, tiff} allowed!" % format, file=sys.stderr)


class AutoPublisher:

    def __init__(self, account_file=None, submit_text_file=None, path=None, verbose=False):

        self.verbose = verbose
        self.log = []
        self.published_accounts = []
        self.path = path
        self.uploaded_images = {}

        self.publish_data = \
        {
            "publish_accounts" : [],
            "failed_accounts" : 0,
            "failed_articles": 0,
            "failed_images" : 0
        }

        self.accounts = self._get_accounts(path + account_file)

        texts = self._get_text(path + submit_text_file)
        self.articles = self._parse_text(texts)

        self.publish_accounts, self.images = self._merge_text_and_accounts()

        if verbose:
            print("\n\nAccounts to be published to:")
            for account in self.publish_accounts:
                print(account)
            print("\n\nImportant notice:")
            for log in self.log:
                print(log)

    def publish(self):
        self._upload_images()
        self._update_image_ref()
        self._upload_articles()

    def _upload_images(self):
        for account in self.accounts:

            client = Client()
            client.access_token = account.token

            try:
                user = client.get_current_user()
            except MediumError:
                continue

            account.client = client
            account.user = user


            for article in account.articles:

                if self.uploaded_images.get(account.name) is None:
                    self.uploaded_images[account.name] = dict()

                for image in article.images:
                    image_global_adress = self.uploaded_images[account.name].get(image)
                    if image_global_adress is None:

                        full_image = self.path + IMAGES_PATH + image
                        if not os.path.isfile(full_image):
                            print("Could not find an image %s in the address %s!" % (image, self.path + IMAGES_PATH),
                                  file=sys.stderr)
                            self.publish_data["failed_images"] += 1
                            continue
                        try:
                            result = client.upload_image(full_image, "image/" + image.split(".")[-1])
                            self.uploaded_images[account.name][image] = result["url"]

                        except MediumError:
                            if self.verbose:
                                print(
                                    "Could not publish image for account %s for article %s. Check the correctness of the format!\n" % (
                                    account.name, article.title))
                            self.publish_data["failed_images"] += 1

    def _update_image_ref(self):

        for account in self.accounts:

            articles = []

            for article in account.articles:
                articleNew = copy.deepcopy(article)
                text = ""
                for text_line in articleNew.text:
                    preped_line = text_line.replace(" ", "").split(":")
                    if preped_line[0] == "IMAGE" and len(preped_line) >= 2:
                        image = "".join(preped_line[1:])
                        account_images = self.uploaded_images.get(account.name)
                        if account_images is not None:
                            image_global_adress = account_images.get(image)
                            if image_global_adress is not None:
                                text += '<img src="%s", alt="Could not load the picture">' % image_global_adress
                            else:
                                text += '<img src="EMPTY", alt="Could not load the picture">'
                    else:
                        text += text_line + "\n"

                content = ""
                content += "<h2>%s</h2>" % articleNew.title
                content += "<p>%s</p>" % text.replace("\n", "<br />")

                articleNew.content = content

                articles += [articleNew]

            account.articles = articles

    def _upload_articles(self):

        uploded_images = {}

        for account in self.publish_accounts:

            published_articles = []

            client = account.client
            user = account.user

            if client is None:
                if self.verbose:
                    print(
                        "Could not access account %s. Check the correctness of the format!\n" %
                            account.name)
                self.publish_data["failed_accounts"] += 1
                continue

            for article in account.articles:

                try:
                    post = client.create_post(user_id=user["id"], title=article.title, content=article.content,
                                              content_format="html")
                    pass
                except MediumError:
                    if self.verbose:
                        print(
                            "Could not publish for account %s an article titled %s. Check the correctness of the format!\n" % (
                            account.name, article.title))
                    self.publish_data["failed_articles"] += 1
                    continue

                published_articles += [article.title]

            self.publish_data["publish_accounts"] += [{"account": account.name, "articles": published_articles}]

        if self.verbose:
            print("Published from accounts:")
            for data in self.publish_data["publish_accounts"]:
                print("List of published articles from account name: %s " % data["account"])
                for article in data["articles"]:
                    print(article)
        print("\n\nFailed to publish from {} accounts, {} articles, {} images".format(
            self.publish_data["failed_accounts"], self.publish_data["failed_articles"],
            self.publish_data["failed_images"]))

    def _get_accounts(self, file_name):

        accounts_file = open(file_name, "r", encoding="utf-8")

        accounts_lines = accounts_file.readlines()

        accounts_file.close()
        accounts = []

        for account_str in accounts_lines:

            if account_str == "\n":
                continue

            account = Account(account_str)
            if account.token is not None and account.language is not None:
                accounts += [account]

        return accounts

    def _get_text(self, file_name):

        with open(file_name, "r") as text_file:

            txt_lines = text_file.readlines()
            texts = []
            buff = []

            for txt_line in txt_lines:
                if txt_line[-1] == "\n":
                    txt_line = txt_line.rstrip()

                if txt_line == "%%%":
                    if buff:
                        texts += [buff]
                    buff = []
                else:
                    buff += [txt_line]

            if buff != [["\n"]] and buff:
                texts += [buff]

            return texts

    def _parse_text(self, texts):

        articles = []

        for text in texts:
            article = Article(text)

            articles += [article]

        return articles

    def _merge_text_and_accounts(self):

        articles_for_language = dict()
        images = dict()
        publish_accounts = []

        for article in self.articles:
            found_articles = articles_for_language.get(article.language)
            if found_articles is None:
                articles_for_language[article.language] = [article]
            else:
                articles_for_language[article.language] = found_articles + [article]

        for account in self.accounts:
            target_language = account.language
            found_articles = articles_for_language.get(target_language)
            if found_articles is None:
                self.log.append("Possible error: could not find article for account name %s" % account.name)
            else:
                account.articles = found_articles
                publish_accounts += [account]

        return publish_accounts, images







if __name__ == "__main__":

    # print("Please check that the following files exist on PATH %s:" % PATH,
    #       "\t 'accountsInfo.txt' storing information about accounts",
    #       "\t'submitText.txt' storing text to publish",
    #       "\t all images are located in 'images/' folder", sep="\n")
    # print("If you wish to modify locations, please enter 'modify', anything else to continue")
    #
    # answer = str(input())
    #
    # if answer == "modify":
    #     while True:
    #         print("You chosed to modify run parameters",
    #               "Please enter ['path' {new_local_path}] to change location of run files",
    #               "Please enter ['accountsInfo' {new_file_name}] to change accounts info file name",
    #               "Please enter ['submitText' {new_file_name}] to change publish text file name",
    #               "Please enter ['images' {new_path_to_images}] to change location of image folder",
    #               "Please enter 'stop' when you are finished", sep="\n")
    #
    #         answer = str(input())
    #
    #         if answer == "stop":
    #             break
    #         elif len(answer.split()) == 2:
    #             if answer.split()[0] == "path":
    #                 PATH = answer.split()[1]
    #             elif answer.split()[0] == "accountsInfo":
    #                 ACCOUNT_INFO = answer.split()[1]
    #             elif answer.split()[0] == "submitText":
    #                 SUBMIT_TEXT_FILE = answer.split()[1]
    #             elif answer.split()[0] == "images":
    #                 IMAGES_PATH = answer.split()[1]

    auto_publisher = AutoPublisher(ACCOUNT_INFO, SUBMIT_TEXT_FILE, path=PATH, verbose=True)

    print("\nEnter 'ok' to continue, anything else to abort")
    answer = str(input())

    if answer == "ok":
        auto_publisher.publish()
        print("\n\nPublished!")
