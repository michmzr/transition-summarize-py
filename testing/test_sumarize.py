import pytest

from summary.summary import summarize, SUMMARIZATON_TYPE

LONG_TEXT = """
"Cześć, Damian Bartiński z klubu Serpentes. Brazylijskie jiu-jitsu swoją tożsamość zawdzięcza technikom, które dość mocno rozwinęły się w parterze. Wielość technik, rozwiązań, pozycji powoduje to, że brazylijskie jiu-jitsu jeżeli chodzi o parter nie ma sobie równa. Należy jednak pamiętać, że każda walka zaczyna się w postawie stojącej. W razylijskim jiu-jitsu przepisy sportowe umożliwiają rozpoczęcie walki od razu w parterze, to znaczy wciąganie do gardła. Jeżeli chodzi o różne formuły sportowe, takie jak zapasy, MMA, brazylijskie jiu-jitsu czy grappling, samo sprowadzenie do parteru jest punktowane, więc można już zyskać przewagę. Jeżeli mówimy o sytuacji takiej realnej samoobrony, to nie wyobrażam sobie, żeby w inny sposób rozpoczynać walkę jak w postawie stojącej. Jednym z podstawowych sposobów składań do parteru stosowanym, właściwie zaczerpniętym zapasów są sprowadzenia uchwytem za nogi. Dzisiaj się tym zajmiemy, będzie to atak na dwie nogi na nisko. W taki sposób zmodyfikowany, aby móc kontynuować walkę w pozycji parterowej, czyli takiej, w której my jako zawodnicy brazylijskiego jiu-jitsu czujemy się najlepiej. Zapraszam do oglądania. Pierwsze, co robimy, to jest umiejętność zajmowania pozycji po opaleniu, czyli takie mikro sprowadzenie za nogi. Czyli obejmuję nogi gdzieś na wysokości kolan, głowę w boku i teraz zobaczcie, za nogi wyraźnie idę do boku. Głowa z boku, pcham w przeciwną stronę, obijam nogi, klaska na klasku. Pierwsze ćwiczenie. Pierwsze ćwiczenie. Ręce szeroko i teraz zobaczcie, dojście jest na wprost, położyłem głowę z boku. Teraz jak mam głowę z boku, to z nogi dalszej odpycham się w tamtą stronę. Jeszcze raz. I teraz to pchnięcie ma być takim ruchem przedłużonym. Co to znaczy? To nie ma być tak, że stanąłem i takie pierwsze pchnięcie zrobiłem, że aż stopa moja straciła kontakt z podłożem i koniec. Nie, nie, nie. Czyli dochodzę, jedna strona, wyraźnie na bok. I taki podstawowy błąd, który się pojawia, to jeżeli ktoś za mocno bije barkiem w brzuch. Czyli jakby za bardzo idzie tam. To jest wyraźnie. Jak on jest wychylony, to gdzieś mniej więcej w tym miejscu ma środek ciężkości. Więc w to miejsce stawiam kolano. Czyli obniżam się, w to miejsce stawiam kolano i dochodzę sobie do... Nawet rękoma go teraz nie chce. Tak, czyli kolano wchodzi pod środek ciężkości, klata do przodu. Zobaczcie, jak jest ustawiona ta stopa. To podłudzie. Jakbym postawił tak, to nie jestem w stanie się w niego pchać. A ja, to nie jestem w stanie się w niego pchać. I tak, to jest tak. I w ten sposób, że ja jestem w środku. I stawiam kolano. I tak. I tak. I tak. I tak. I tak. Jakbym postawił tak, to nie jestem w stanie się w niego pchać. A ja przecież z tej nogi będę pchał się w niego. Czyli jest. Dochodzę sobie, obniżam. Klata blisko, wzrok skierowany do przodu. Dochodzę sobie do dwóch nóg. I patrzę, czy on się odrywa. Jeżeli będę za głęboko kolanem z przodu, będę się przelaczał do tyłu. Jeżeli będę za bardzo kolanem z tyłu, to go w ogóle nie dźwignę. Jeżeli nie będę miał doklejonego ucha do biodra, to mi spadnie do boku. I to pokazuje, czy to poprzednie ćwiczenie zostało zrobione dobrze. Jeszcze raz. Zobaczcie. Dochodzę sobie, złapałem. Prostuję się. Jest ok. Muzyka Czyli dochodzę sobie do nóg. Wysoko. Jeszcze raz. Dla jednego, dla drugiego przyjemnie. Muzyka Muzyka Teraz już nie będziemy tylko dźwigali z grzbietu. Bo przed chwilą to było samo grzbiet. A teraz jeszcze sobie dołożymy nogę. Czyli ta, na której stoję, to ona będzie miała siłę do tego, żeby mnie przewracać. Grzbiet. Czyli... Zobacz. Czyli idę na dwie nogi. Pamiętamy, na wprost. Głowa spycha na bok, idę do boczni. Czyli doszedłem sobie do boczni. Jeszcze raz. Klata do przodu, głęboko, zgięcia łokciowe łapią nogę. Uchem spycham, wkładam sobie do boku, odprowadzając nogi na bok. Dochodzę sobie. Muzyka Muzyka Muzyka Jesteśmy już po treningu. Tak jak mówiłem, przerabialiśmy sobie techniki i były ataki do nóg. Oczywiście każdy trening kończymy sparingami. Widać po mnie, że każdy daje z siebie wszystko. Każdy chce wygrać. Każdy chce sobie przerobić to, co zrobił podczas treningu. Jeśli Wam się podobało, dajcie łapki w górę. Oczywiście jeżeli chcecie na bieżąco być z naszym kanałem, to zasubskrybujcie oczywiście dzwoneczek, żeby powiadomienia się pojawiały. Jeżeli chodzi o następny film, który będzie w przyszłym tygodniu, będą to obrony przed atakami do nóg. Czyli krótko mówiąc jak zatrzymać zapaśnika. Bo zdarzają się takie sytuacje, zwłaszcza na zawodach, gdzie ktoś ma doświadczenie zapaśnicze i stosunkowo mocną stójkę. I do tego właśnie będą potrzebne te obrony. Po to, żeby zacząć grać w swoją grę, czyli parter, to czym czujemy się najlepiej, najswobodniej. Zapraszam do oglądania następnym razem.
"""


def test_tldr_summarize():
    summmary = summarize(LONG_TEXT, "TLDR")
    assert summmary != ""
