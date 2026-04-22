import re
import os


def find_etymologies(article_body: str):
    """
    Поиск этимологических сведений в теле статьи.

    Разбор решулярного выражения:

    - (?s) — это встроенный флаг re.DOTALL. Он нужен для того, чтобы символ точки . мог захватывать переносы строк (\n), если этимология в файле разбита на несколько строк.
    
    - (?:Фр|Лат|Нем|Малаб|Голл|Ит|Итал|Пол|Польск|Англ|Греч|Исп) — это группа без сохранения, начало регулярного выражения

    - .*? — это ленивый захват любого текста (чтобы не проглотить полфайла).

    (?=<hi|</p>) — это позитивный просмотр вперед (positive lookahead): останавливается на <hi или </p>, но сами эти теги в итоговый результат не включает.
    """

    etym_pattern = re.compile('(?s)(?:Фр|Лат|Нем|Малаб|Голл|Ит|Итал|Пол|Польск|Англ|Греч|Исп).*?(?=<hi|</p>)')

    etym_match = etym_pattern.search(article_body)

    if etym_match:
        return etym_match.group(0)
    else:
        return 'Этимологических сведений не найдено'


def go_through_articles(dir: str):
    """
    Проход по папке с отпарсенными словарными статьями в html-формате
    """
    articles = os.listdir(dir)
    
    for article in articles:
        if article[-4:] == 'html':
            
            with open(os.path.join(dir, article), encoding='utf-8') as file:
                article_body = file.read()

            etymology = find_etymologies(article_body)

            print('-'*30)
            print(article)
            print(etymology)


article_example = """<p> <hi rendition="simple:bold">БЕТЕЛЬ</hi> 1766, я и ю,
<hi rendition="simple:italic">м</hi>. Малаб. vettila, через фр. bétel,
нем Betel. <hi rendition="simple:italic">Сорт перца</hi>. Жуют противную
траву бетель. Мод. госп. 14. Бетель есть растение, славное во всей Азии,
а особливо в Ост-Индии, котораго листы наполнены красным соком. Приб. МВ
1783 237. <hi rendition="simple:bold">Бетелев,</hi> а, о. Индѣйцы жуют
листы Бетелевы. Сл. комм. I 177.</p>"""

# print(find_etymologies(article_example))

go_through_articles('data\samples_html')