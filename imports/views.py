from taxa import models, helpers
from redlist import models as redlist_models
from people import models as people_models
import pandas as pd
from imports import sis_import, spstatus_import, sarca_sabca
from imports import sis_import, spstatus_import
from imports import seakeys as seakeys_import
import json
import os
import datetime
import csv
import requests
from django.contrib.gis.geos import Point, Polygon
from django.utils.text import slugify


# Run after all of the imports have gone through to get common names for classes, families, etc
def populate_higher_level_common_names(request):
    ranks = models.Rank.objects.filter(name__in=['Genus', 'Family', 'Order', 'Phylum', 'Class'])
    taxa = models.Taxon.objects.filter(rank__in=ranks, common_names__isnull=True)
    english = models.Language.objects.get(name='English')

    # Manually found some nodes common names
    pwd = os.path.abspath(os.path.dirname(__file__))
    common_names = {}
    with open(os.path.join(pwd, '..', 'data-sources', 'common_names.csv')) as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            common_names[row[0]] = row[1]

    for taxon in taxa:
        taxon_name = taxon.name.lower()

        # Try and get it in my list first
        if taxon_name in common_names:
            common_name = models.CommonName.objects.get_or_create(name=common_names[taxon_name], taxon=taxon, language=english)
            continue
        continue
        # Otherwise search GBIF
        r = requests.get('http://api.gbif.org/v1/species/search?q=' + taxon.name.lower() + '&rank=' + str(taxon.rank))
        gbif = r.json()
        print('-----')
        try:
            print(taxon.name.lower())
        except:
            print('could not print')
        #import pdb; pdb.set_trace()
        try:
            for result in gbif['results']:
                if 'vernacularNames' in result and len(result['vernacularNames']) > 0:
                    for vn in result['vernacularNames']:
                        if vn['language'].lower() == '' or vn['language'].lower() == 'english':
                            common_name_text = vn['vernacularName'] # Reasonable to assume english?
                            common_name = models.CommonName.objects.get_or_create(name=common_name_text, taxon=taxon, language=english)
                            print('GBIF ' + taxon.name.lower() + ' : ' + common_name_text)
                            break
        except (KeyError, IndexError, UnicodeDecodeError, UnicodeEncodeError):
            import pdb; pdb.set_trace()
        # common_name.save()

    #r = requests.get('http://api.gbif.org/v1/species?' + )
    #r.json()


# SIS: Amphibian, Mammals, Dragonflies, Reptiles, Freshwater Fish
def sis(request):
    sis_import.import_sis()


# Butterflies
def sarca(request):
    sarca_sabca.import_sql()


# Legacy data - we're not importing this, it's not used.
def spstatus(request):
    spstatus_import.import_spstatus()


# Linefish
def seakeys(request):
    seakeys_import.import_seakeys()


def lc_birds(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources')
    birds = pd.read_csv(os.path.join(dir, 'birds.csv'), encoding='iso-8859-1')

    # Get the least concern birds and add genus
    lc_birds = birds.loc[birds['Regional Red List Status_2015'] == 'LC']
    lc_birds['genus'] = lc_birds['Scientific Name'].str.split(' ').apply(lambda x: x[0])

    # Fix columns so they're lowercase with no spaces
    lc_birds.columns = map(lambda x: x.lower().replace(' ', ''), lc_birds.columns)

    # Get some of the db objects used in the for loop
    aves = models.Taxon.objects.get(name='Aves')
    english = models.Language.objects.get(name='English')
    subspecies_rank = models.Rank.objects.get(name='Subspecies')
    species_rank = models.Rank.objects.get(name='Species')
    genus_rank = models.Rank.objects.get(name='Genus')
    family_rank = models.Rank.objects.get(name='Family')
    order_rank = models.Rank.objects.get(name='Order')

    # Iterate over all LC birds and create taxa & redlist objects for them
    for index, bird in lc_birds.iterrows():
        print('doing ' + bird['scientificname'])
        name_parts = bird['scientificname'].split(' ')
        genus = name_parts[0]
        order, created = models.Taxon.objects.get_or_create(name=bird['odr'], rank=order_rank, parent=aves)
        family, created = models.Taxon.objects.get_or_create(name=bird['family'], rank=family_rank, parent=order)
        parent, created = models.Taxon.objects.get_or_create(name=genus, rank=genus_rank, parent=family)

        # Special case for subspecies
        if len(name_parts) > 2:
            species = models.Taxon.objects.create(name=name_parts[0] + ' ' + name_parts[1], rank=species_rank, parent=parent)
            node = models.Taxon.objects.create(name=' '.join(name_parts), rank=subspecies_rank, parent=species)
        else:
            node = models.Taxon.objects.create(name=' '.join(name_parts), rank=species_rank, parent=parent)

        models.CommonName.objects.create(language=english, name=bird['fullname'], taxon=node)
        redlist_models.Assessment.objects.create(taxon=node, date=datetime.date(year=2015, month=1, day=1), redlist_category=redlist_models.Assessment.LEAST_CONCERN)


# Note: Birds are run from the other django app
def bird_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_bird')
    bird_parent_node = models.Taxon.objects.get(name='Aves')
    species_rank = models.Rank.objects.get(name='Species')
    subspecies_rank = models.Rank.objects.get(name='Subspecies')
    birds = bird_parent_node.get_descendants().filter(rank__in=[species_rank, subspecies_rank])
    for bird in birds:
        bird_file = os.path.join(dir, bird.name.replace(' ', '_') + '.json')
        if not os.path.exists(bird_file):
            continue

        with open(bird_file) as data_file:
            distributions = json.load(data_file)

            for distribution in distributions['features']:
                polygon_points = []
                for ring in distribution['geometry']['rings'][0]:
                    polygon_points.append((ring[0], ring[1]))
                polygon_tuple = tuple(polygon_points)
                polygon = Polygon(polygon_tuple, srid=4326)
                distrib = models.GeneralDistribution(taxon=bird, distribution_polygon=polygon)
                distrib.save()


def ffish_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_freshwater_fish')

    classes = ['Actinopterygii', '']
    parent_node = models.Taxon.objects.get(name='Chordata')
    species_rank = models.Rank.objects.get(name='Species')
    subspecies_rank = models.Rank.objects.get(name='Subspecies')
    nodes = parent_node.get_descendants().filter(rank__in=[species_rank, subspecies_rank])

    for node in nodes:
        node_file = os.path.join(dir, node.name.capitalize() + '.json')
        if not os.path.exists(node_file):
            continue
        print('found ' + node_file)
        with open(node_file) as data_file:
            distributions = json.load(data_file)
            for distribution in distributions['features']:
                if distribution['geometry']['type'] == 'Polygon':
                    polygon_points = []
                    for ring in distribution['geometry']['coordinates'][0]:
                        polygon_points.append((ring[0], ring[1]))
                    polygon_tuple = tuple(polygon_points)
                    polygon = Polygon(polygon_tuple, srid=4326)
                    print('creating distrib for ' + node.name)
                    distrib = models.GeneralDistribution(taxon=node, distribution_polygon=polygon)
                    distrib.save()
                elif distribution['geometry']['type'] == 'MultiPolygon':
                    for ring in distribution['geometry']['coordinates']:
                        polygon_points = []
                        for wtf in ring[0]:
                            polygon_points.append((wtf[0], wtf[1]))
                        polygon_tuple = tuple(polygon_points)
                        polygon = Polygon(polygon_tuple, srid=4326)
                        print('creating distrib for ' + node.name)
                        distrib = models.GeneralDistribution(taxon=node, distribution_polygon=polygon)
                        distrib.save()


def frog_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    '''
    # Do the points first
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_frog_pts')
    df = pd.read_csv(os.path.join(dir, 'simple.csv'), encoding='latin-1')
    mapping = {'decimallatitude': 'lat',
               'decimallongitude': 'long',
               'institution source': 'origin_code',
               'specificepithet': 'species'}
    df.columns = map(str.lower, df.columns)
    df.rename(columns=mapping, inplace=True)
    df = df.loc[df['taxonrank'].isin(['species', 'Subspecies'])]
    for index, row in df.iterrows():
        name_parts = row['scientificname'].strip().split(' ')
        row['species'] = name_parts[1]
        if len(name_parts) > 2:
            row['subspecies'] = name_parts[2]
        pt = create_point_distribution(row)

    import pdb; pdb.set_trace()'''

    # Then the polygons
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_frog')
    parent_node = models.Taxon.objects.get(name='Amphibia')
    species_rank = models.Rank.objects.get(name='Species')
    subspecies_rank = models.Rank.objects.get(name='Subspecies')
    nodes = parent_node.get_descendants().filter(rank__in=[species_rank, subspecies_rank])

    for node in nodes:
        node_file = os.path.join(dir, node.name.replace(' ', '_') + '.json')
        if not os.path.exists(node_file):
            continue
        print('found ' + node_file)
        with open(node_file) as data_file:
            distributions = json.load(data_file)

            for distribution in distributions['features']:
                polygon_points = []
                for ring in distribution['geometry']['rings'][0]:
                    polygon_points.append((ring[0], ring[1]))
                polygon_tuple = tuple(polygon_points)
                polygon = Polygon(polygon_tuple, srid=4326)
                distrib = models.GeneralDistribution(taxon=node, distribution_polygon=polygon)
                distrib.save()


# Gets all the butterfly 'broken' criteria strings and fix them
def convert_all_criteria_strings(request):
    needs_fixing = redlist_models.Assessment.objects.filter(redlist_criteria__contains='|')

    for assessment in needs_fixing:
        try:
            assessment.redlist_criteria = convert_criteria_string(assessment.redlist_criteria)
        except IndexError:
            import pdb; pdb.set_trace()
        assessment.save()

    needs_fixing = people_models.Person.objects.all()
    for person in needs_fixing:
        person.slug = slugify(str(person))
        person.save()


# Used to fix the criteria string in the butterfly/sabca db imports
def convert_criteria_string(string):
    # Construct a load of nested dictionaries with all of the individual components
    cons = {}
    for item in string.split('|'):
        # B
        letter = item[0].upper()
        if letter not in cons:
            cons[letter] = {} # cons = {'B' => {}}

        # B1, sometimes you just have D with no number
        if len(item) > 1:
            number = item[1]
            if number not in cons[letter]:
                cons[letter][number] = {} #  cons = {'B' => {}}

            # B1a or B1b_iii, sometimes you just have D1 with no letter
            if len(item) > 2:
                small_letter = item[2].lower()
                if small_letter not in cons[letter][number]:
                    cons[letter][number][small_letter] = []

                if '_' in item:
                    roman_numerals = item.split('_')[1]
                    if roman_numerals not in cons[letter][number][small_letter]:
                        cons[letter][number][small_letter].append(roman_numerals)

    # Following is not used, just an example of what we're constructing
    # output_example = {'A': {'2': {'a': [], 'b': []}}, 'B': {'1': {'a': [], 'b': ['i', 'ii', 'iii']}}}

    # Join those dictionaries together, we also need to do some sorting once they are lists
    letter_strings = []
    for letter, number_dict in cons.items():
        number_strings = []

        for number, small_letter_dict in number_dict.items():
            small_letter_strings = []

            for small_letter, roman_numerals_list in small_letter_dict.items():
                small_letter_string = small_letter
                if roman_numerals_list:
                    small_letter_string += '(' + ','.join(roman_numerals_list) + ')'
                small_letter_strings.append(small_letter_string)

            # small_letter_string now looks like this: 'ab(i,ii,iii)'
            number_strings.append(number + ''.join(sorted(small_letter_strings)))

        # number_strings now looks like this ['2ab(i,ii,iii)', '1a']
        letter_strings.append(letter + '+'.join(sorted(number_strings)))

    # letter_strings now looks like this ['A2ab(i,ii,iii)', 'C1a']

    return '; '.join(sorted(letter_strings))


def create_point_distribution(row):
    """
    Used by the import distribution functions
    Ok this really needs to get refactored at some point. First there should be a get_species function
    then the create_point_distribution function should contain long, lat, species,
    [precision, origin_code, qds, year, month, day (optional)]
    """
    if 'species' not in row or 'genus' not in row or 'long' not in row or 'lat' not in row:
        import pdb; pdb.set_trace()
        return False

    try:
        name = row['genus'].strip() + ' ' + row['species'].strip()
    except:
        return False

    if 'subspecies' in row and row['subspecies'] != 0 and pd.isnull(row['subspecies']) == False:
        print(row['subspecies'])
        try:
            name += ' ' + row['subspecies'].strip()
        except:
            import pdb; pdb.set_trace()

    try:
        taxon = models.Taxon.objects.get(name=name)
        print('found ' + name)
    except models.Taxon.DoesNotExist:
        print('could not find ' + name)
        return False
    except models.Taxon.MultipleObjectsReturned:
        import pdb; pdb.set_trace()

    try:
        if not row['long'] or pd.isnull(row['long']) or str(row['long']).strip() == '' or len(str(row['long']).strip()) == 0:
            return False
        if not row['lat'] or pd.isnull(row['lat']) or str(row['lat']).strip() == '' or len(str(row['lat']).strip()) == 0:
            return False
        pt = models.PointDistribution(taxon=taxon, point=Point(float(row['long']), float(row['lat'])))
        optional_fields = ['precision', 'origin_code', 'qds']
        for optional_field in optional_fields:
            if optional_field in row:
                setattr(pt, optional_field, row[optional_field])

        if 'year' in row and row['year'] > 0:
            month = int(float(str(row['month']).strip())) if 'month' in row else 1
            month = month if month > 0 and month < 13 else 1
            day = int(float(str(row['day']).strip())) if 'day' in row else 1
            day = day if day > 0 and day < 31 else 1
            try:
                pt.date = datetime.date(year=int(float(str(row['year']).strip())), month=month, day=day)
            except ValueError:
                pass
        pt.save()
    except:
        return False

    return pt


def reptile_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_reptile')
    parent_node = models.Taxon.objects.get(name='Reptilia')
    species_rank = models.Rank.objects.get(name='Species')
    subspecies_rank = models.Rank.objects.get(name='Subspecies')
    nodes = parent_node.get_descendants().filter(rank__in=[species_rank, subspecies_rank])

    for node in nodes:
        node_file = os.path.join(dir, node.name.replace(' ', '_').capitalize() + '.json')
        if not os.path.exists(node_file):
            continue
        print('found ' + node_file)
        with open(node_file) as data_file:
            distributions = json.load(data_file)

            for distribution in distributions['features']:
                if distribution['geometry']['type'] == 'Polygon':
                    polygon_points = []
                    for ring in distribution['geometry']['coordinates'][0]:
                        polygon_points.append((ring[0], ring[1]))
                    polygon_tuple = tuple(polygon_points)
                    polygon = Polygon(polygon_tuple, srid=4326)
                    print('creating distrib for ' + node.name)
                    distrib = models.GeneralDistribution(taxon=node, distribution_polygon=polygon)
                    distrib.save()
                elif distribution['geometry']['type'] == 'MultiPolygon':
                    for ring in distribution['geometry']['coordinates']:
                        polygon_points = []
                        for wtf in ring[0]:
                            polygon_points.append((wtf[0], wtf[1]))
                        polygon_tuple = tuple(polygon_points)
                        polygon = Polygon(polygon_tuple, srid=4326)
                        print('creating distrib for ' + node.name)
                        distrib = models.GeneralDistribution(taxon=node, distribution_polygon=polygon)
                        distrib.save()


def reptile_distribs_old(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_reptile')
    df = pd.read_csv(os.path.join(dir, 'simple.csv'), encoding='latin-1')
    mapping = {'decimallat': 'lat',
               'decimallon': 'long',
               'institutio': 'origin_code',
               'year_colle': 'year',
               'month_coll': 'month',
               'day_collec': 'day'}
    df.columns = map(str.lower, df.columns)
    df.rename(columns=mapping, inplace=True)
    print('renamed columns')
    for index, row in df.iterrows():
        print(index)
        pt = create_point_distribution(row)


def dragonfly_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_dragonfly')
    df = pd.read_csv(os.path.join(dir, 'simple.csv'))
    mapping = {'decimal_latitude': 'lat',
               'decimal_longitude': 'long',
               'institution_code': 'origin_code',
               'coordinate_uncertainty_in_meters': 'precision',
               'year_collected': 'year',
               'month_collected': 'month',
               'day_collected': 'day'}
    df.columns = map(str.lower, df.columns)
    df.rename(columns=mapping, inplace=True)
    for index, row in df.iterrows():
        print(index)
        pt = create_point_distribution(row)


def mammal_distribs(request):
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_mammal')
    mapping = {'decimallatitude': 'lat',
               'decimallongitude': 'long',
               'institutioncode': 'origin_code',
               'coordinateuncertaintyinmeters': 'precision',
               'specificepithet': 'species'}
    for file in os.listdir(dir):
        print(file)
        df = pd.read_excel(os.path.join(dir, file))
        df.columns = map(str.lower, df.columns)
        # Fix for #56
        df.loc[pd.isnull(df['institutioncode']), 'institutioncode'] = df.loc[pd.isnull(df['institutioncode']), 'recordedby']
        df.rename(columns=mapping, inplace=True)
        for index, row in df.iterrows():
            print(index)
            #pt = create_point_distribution(row)


def butterfly_distribs(request):
    # Note this function is a bit different as there is already butterfly distribution data in the db
    # from fhatani's sarca/sabca script. So first all previous distribution points for that species must be deleted
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'data-sources', 'distribs_butterfly')
    df = pd.read_csv(os.path.join(dir, 'simple.csv'), encoding='latin1')
    extract = df['rec_date'].str.extract('^(\d{4})-(\d\d)-(\d\d)')
    df['year'], df['month'], df['day'] = extract[0], extract[1], extract[2]

    # Delete distributions for all non-LC butterflies
    distinct_names = {}
    for name in df['new_name'].unique():
        try:
            taxon = models.Taxon.objects.get(name=name)
            taxon.general_distributions.delete()
            taxon.point_distributions.delete()
            distinct_names[name] = taxon
        except models.Taxon.DoesNotExist:
            print('could not find ' + name)
            return False
        except models.Taxon.MultipleObjectsReturned:
            import pdb; pdb.set_trace()

    for index, row in df.iterrows():
        pt = models.PointDistribution(taxon=distinct_names[row['new_name']], point=Point(float(row['SUGGESTED_GPS_NS']), float(row['SUGGESTED_GPS_EW'])))
        if row['REC_SOURCE']:
            pt.origin_code = row['REC_SOURCE']
        pt.date = datetime.date(year=row['year'], month=row['month'], day=row['day'])
        pt.save()


def st_process(request):
    """Exclude all distribution points falling within an ocean (oceans.json contains polygons)"""
    pwd = os.path.abspath(os.path.dirname(__file__))
    dir = os.path.join(pwd, '..', 'website', 'static')

    # Load the ocean polygons into a list of polygons
    oceans = os.path.join(dir, 'oceans.json')
    with open(oceans) as data_file:
        distributions = json.load(data_file)
    for distribution in distributions['features']:
        polygons = []
        for ring in distribution['geometry']['rings']:
            polygon_points = []
            for point in ring:
                polygon_points.append((point[0], point[1]))
            polygon_tuple = tuple(polygon_points)
            polygons.append(Polygon(polygon_tuple, srid=4326))

    # get first polygon
    polygon_union = polygons[0]

    # update list to include all other polygons but the first
    polygons = polygons[1:]

    # loop through list of polygons and union them together
    for poly in polygons:
        polygon_union = polygon_union.union(poly)

    # Retrieve a list of points falling within the oceans and delete them
    points_for_deleting = models.PointDistribution.objects.filter(point__within=polygon_union)
    points_for_deleting.delete()


def clean_origin_codes(request):
    auditors_report()
    import pdb; pdb.set_trace()
    pwd = os.path.abspath(os.path.dirname(__file__))
    file = os.path.join(pwd, '..', 'data-sources', 'distribution_attributions.csv')
    df = pd.read_csv(file, encoding='latin-1') #  encoding='latin-1'
    for index, mapping in df.iterrows():
        models.PointDistribution.objects.filter(origin_code=mapping['institution_code']).update(origin_code=mapping['use'])


#def auditors_report():
def auditors_report(request):
    # This has come to be a general purpose report type function, there's some random stuff in here
    import csv
    pwd = os.path.abspath(os.path.dirname(__file__))
    url = 'http://speciesstatus.sanbi.org/assessment/last-assessment/'

    # This is used in almost all the stats/reports generated
    ranks = models.Rank.objects.filter(name__in=['Species', 'Subspecies'])
    order_rank = models.Rank.objects.get(name='Order')
    class_rank = models.Rank.objects.get(name='Class')

    # The script below prints out all freshwater species to a csv
    with open(os.path.join(pwd, '..', 'freshwater.csv'), 'w', newline='') as csvfile:
        dwriter = csv.writer(csvfile)
        freshwater_str = 'Freshwater (=Inland waters)'
        fresh_species = models.Taxon.objects.filter(info__habitat_narrative__icontains = freshwater_str)
        for species in fresh_species:
            csv_args = []

            # Assessment info
            assessment = species.get_latest_assessment()
            csv_args.append(assessment.redlist_category)
            csv_args.append(assessment.redlist_criteria)
            csv_args.append(assessment.rationale)
            csv_args.append(assessment.scope)
            csv_args.append(assessment.threats_narrative)

            # Threat codings
            threats = redlist_models.ThreatNature.objects.filter(assessment=assessment).values_list('threat__name', flat=True)
            threats_str = '|'.join(threats)
            csv_args.append(threats_str)


            # Append all taxonomic levels for this sp
            ancestors = species.get_ancestors().values_list('name', flat=True)
            for ancestor in ancestors:
                csv_args.append(ancestor)

            dwriter.writerow(csv_args)

        import pdb; pdb.set_trace()

    return

    # The script below prints to 2 csvs the species with no images and no distributions
    with open(os.path.join(pwd, '..', 'no_distributions.csv'), 'w', newline='') as csvfile, \
            open(os.path.join(pwd, '..', 'no_images.csv'), 'w', newline='') as noimagefile:
        dwriter = csv.writer(csvfile)
        dwriter.writerow(['order', 'class', 'scientific_name', 'redlist status', 'url'])
        iwriter = csv.writer(noimagefile)
        iwriter.writerow(['order', 'class', 'scientific_name', 'redlist status', 'url'])
        classes = models.Taxon.objects.filter(rank=class_rank)
        for class_ in classes:
            orders = class_.get_descendants().filter(rank=order_rank)
            for order in orders:
                species = order.get_descendants().filter(rank__in=ranks)
                species_without_distribs = order.get_descendants().filter(rank__in=ranks, point_distributions__isnull=True, general_distributions__isnull=True)
                for sp in species:
                    assessment = sp.get_latest_assessment()
                    subspecies_count = sp.get_descendant_count()
                    if (subspecies_count == 0 and assessment is None) or subspecies_count != 0:
                        print(sp.name)
                        if 'rosei' not in sp.name and sp.name != 'Myosorex cafer' and 'Heleophryne' not in sp.name:
                            #import pdb; pdb.set_trace()
                            pass
                        continue

                    # Does not have an image
                    csv_args = [order.name, class_.name, sp.name, sp.get_latest_assessment().redlist_category,
                                url + str(sp.pk)]
                    if not has_images(sp.name, class_.name, order.name):
                        iwriter.writerow(csv_args)
                    if sp in species_without_distribs:  # Also does not have a distrib
                        dwriter.writerow(csv_args)

    #birds = models.Taxon.objects.get(name="Aves")
    #bird_sp = birds.get_descendants().filter(rank__in=ranks, point_distributions__isnull=True, general_distributions__isnull=True)
    #with open(os.path.join(pwd, '..', 'threatened-birds.csv'), 'w', newline='') as csvfile:
    #    spamwriter = csv.writer(csvfile)
    #    spamwriter.writerow(['scientific_name', 'redlist status', 'url'])
    #    for bird in bird_sp:
    #        spamwriter.writerow([bird.name, bird.get_latest_assessment().redlist_category, url + str(bird.pk)])
    print('finished')
    import pdb; pdb.set_trace()


    no_points = models.Taxon.objects.filter(rank__in=ranks, point_distributions__isnull=True, general_distributions__isnull=True)

    actin = models.Taxon.objects.get(name='Actinopterygii')
    elas = models.Taxon.objects.get(name='Elasmobranchii')
    holo = models.Taxon.objects.get(name='Holocephali')
    actin_fishes = actin.get_descendants().filter(rank__in=ranks)
    elas_fishes = elas.get_descendants().filter(rank__in=ranks)
    holo_fishes = holo.get_descendants().filter(rank__in=ranks)

    from itertools import chain
    # joined = list(chain(holo_fishes, elas_fishes, actin_fishes))
    url = 'http://speciesstatus.sanbi.org/assessment/last-assessment/'
    with open(os.path.join(pwd, '..', 'fishes.csv'), 'w', newline='') as csvfile:
        spamwriter = csv.writer(csvfile)
        spamwriter.writerow(['scientific_name', 'class', 'redlist status', 'url'])
        for fish in actin_fishes:
            spamwriter.writerow([fish.name, 'Actinopterygii', fish.get_latest_assessment().redlist_category, url + str(fish.pk)])
        for fish in elas_fishes:
            spamwriter.writerow([fish.name, 'Elasmobranchii', fish.get_latest_assessment().redlist_category, url + str(fish.pk)])
        for fish in holo_fishes:
            spamwriter.writerow([fish.name, 'Holocephali', fish.get_latest_assessment().redlist_category, url + str(fish.pk)])

def has_images(taxon, class_, order):
    import subprocess as subp
    from django.conf import settings
    folder = class_.lower()
    if folder == 'actinopterygii' or folder == 'elasmobranchii' or folder == 'holocephali':
        folder = 'fish'
    elif folder == 'insecta':
        folder = order.lower()
    file_name_template = taxon.replace(' ', '_')
    file_location = os.path.join(settings.BASE_DIR, 'website', 'static', 'sp-imgs', folder, file_name_template)
    # Check the file exists, and then extract the IPTC information embedded in the image for attribution & copyright
    # 'thumb': 'sp-imgs/' + taxon.replace(' ', '_') + '__thumb.jpg' - might need to do this later
    i = 1
    file_info = []

    while (os.path.isfile(file_location + '_' + str(i) + '.jpg')):
        file_name = file_name_template + '_' + str(i) + '.jpg'

        # info = p.get_json(file_location + '_' + str(i) + '.jpg')
        # Replacing exiftool code as it doesn't work in IIS
        sb = subp.Popen(['exiftool', '-G', '-j', '-sort', file_location + '_' + str(i) + '.jpg'], stdin=subp.PIPE,
                        stdout=subp.PIPE, stderr=subp.STDOUT)
        s = sb.stdout.read()
        s = s.strip()
        if s:
            s = s.decode('utf-8').rstrip('\r\n')
            info = json.loads(s)
        else:
            s = False

        return_data = {'file': 'sp-imgs/' + folder + '/' + file_name}
        return_data['author'] = 'Unknown' if 'IPTC:By-line' not in info[0] else info[0]['IPTC:By-line']
        return_data['copyright'] = '[None given]' if 'IPTC:CopyrightNotice' not in info[0] else info[0][
            'IPTC:CopyrightNotice']
        return_data['source'] = '' if 'IPTC:Source' not in info[0] else info[0]['IPTC:Source']
        file_info.append(return_data)
        i += 1

    if file_info:
        return True
    else:
        return False