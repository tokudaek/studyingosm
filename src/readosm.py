#!/usr/bin/env python3
"""Parse OSM data
"""

import numpy as np
import argparse
#import osmium
#import shapely.wkb as wkblib
import xml.etree.ElementTree as ET
from rtree import index
import matplotlib.pyplot as plt
import logging
from logging import debug
import random

# Definitions
WAY_TYPES = ["motorway", "trunk", "primary", "secondary", "tertiary",
             "unclassified", "residential", "service", "living_street"]

##########################################################
def get_all_nodes(root, invways):
    """Get all nodes in the xml struct

    Args:
    root(ET): root element 

    Returns:
    rtree.index: rtree of the nodes
    invways(dict): inverted list of ways, i.e., node as key and list of way ids as values
    """
    valid = invways.keys()
    nodesidx = index.Index()
    nodeshash = {}

    for child in root:
        if child.tag != 'node': continue # not node
        if int(child.attrib['id']) not in valid: continue # non relevant node

        att = child.attrib
        lat, lon = float(att['lat']), float(att['lon'])
        nodesidx.insert(int(att['id']), (lat, lon, lat, lon))
        nodeshash[int(att['id'])] = (lat, lon)
    debug('Found {} path nodes'.format(len(nodeshash.keys())))

    return nodesidx, nodeshash

##########################################################
def get_all_ways(root):
    """Get all ways in the xml struct

    Args:
    root(ET): root element 

    Returns:
    dict of list: hash of wayids as key and list of nodes as values;
    dict of list: hash of nodeid as key and list of wayids as values;
    """
    ways = {}
    invways = {} # inverted list of ways

    for way in root:
        if way.tag != 'way': continue
        wayid = int(way.attrib['id'])
        isstreet = False
        nodes = []

        nodes = []
        for child in way:
            if child.tag == 'nd':
                nodes.append(int(child.attrib['ref']))
            elif child.tag == 'tag':
                if child.attrib['k'] == 'highway' and child.attrib['v'] in WAY_TYPES:
                    isstreet = True

        if isstreet:
            ways[wayid]  = nodes

            for node in nodes:
                if node in invways.keys(): invways[node].append(wayid)
                else: invways[node] = [wayid]

    debug('Found {} ways'.format(len(ways.keys())))
    return ways, invways

##########################################################
def idx2array_nodes(nodes_rtree):
    bounds = nodes_rtree.bounds
    nodeslist = list(nodes_rtree.intersection(bounds, objects=True))
    npoints = len(nodeslist)

    nodes = np.ndarray((npoints, 2))

    for i, node in enumerate(nodeslist):
        nodes[i, 0] = node.bbox[0]
        nodes[i, 1] = node.bbox[1]

    return nodes

##########################################################
def render_map(nodeshash, ways, crossings, frontend='bokeh'):
    if frontend == 'matplotlib':
        render_matplotlib(nodeshash, ways, crossings)
    else:
        render_bokeh(nodeshash, ways, crossings)

##########################################################
def get_nodes_coords_from_hash(nodeshash):
    """Get nodes coordinates and discard nodes ids information
    Args:
    nodeshash(dict): nodeid as key and (x, y) as value

    Returns:
    np.array(n, 2): Return a two-column table containing all the coordinates
    """

    nnodes = len(nodeshash.keys())
    nodes = np.ndarray((nnodes, 2))

    for j, coords in enumerate(nodeshash.values()):
        nodes[j, 0] = coords[0]
        nodes[j, 1] = coords[1]
    return nodes

##########################################################
def get_crossings(invways):
    """Get the crossings

    Args:
    invways(dict of list): inverted list of the ways. It s a dict of nodeid as key and
    list of wayids as values

    Returns:
    set: set of crossings
    """

    crossings = set()
    for nodeid, waysids in invways.items():
        if len(waysids) > 1:
            crossings.add(nodeid)
    return crossings

##########################################################
def filter_out_orphan_nodes(ways, invways, nodeshash):
    """Check consistency of nodes in invways and nodeshash and fix them in case
    of inconsistency
    It can just be explained by the *non* exitance of nodes, even though they are
    referenced inside ways (<nd ref>)

    Args:
    invways(dict of list): nodeid as key and a list of wayids as values
    nodeshash(dict of 2-uple): nodeid as key and (x, y) as value
    ways(dict of list): wayid as key and an ordered list of nodeids as values

    Returns:
    dict of list, dict of lists
    """
    ninvways = len(invways.keys())
    nnodeshash = len(nodeshash.keys())
    if ninvways == nnodeshash: return ways, invways

    validnodes = set(nodeshash.keys())

    # Filter ways
    for wayid, nodes in ways.items():
        newlist = [ nodeid for nodeid in nodes if nodeid in validnodes ]
        ways[wayid] = newlist
        
    # Filter invways
    invwaysnodes = set(invways.keys())
    invalid = invwaysnodes.difference(validnodes)

    for nodeid in invalid:
        del invways[nodeid]

    ninvways = len(invways.keys())
    debug('Filtered {} orphan nodes.'.format(ninvways - nnodeshash))
    return ways, invways


##########################################################
def render_matplotlib(nodeshash, ways, crossings):
    # render nodes
    nodes = get_nodes_coords_from_hash(nodeshash)
    plt.scatter(nodes[:, 1], nodes[:, 0], c='blue', alpha=1, s=20)

    # render ways
    for wnodes in ways.values():
        r = lambda: random.randint(0,255)
        waycolor = '#%02X%02X%02X' % (r(),r(),r())
        lats = []; lons = []
        for nodeid in wnodes:
            a, o = nodeshash[nodeid]
            lats.append(a)
            lons.append(o)
        plt.plot(lons, lats, linewidth=2, color=waycolor)

    # render crossings
    crossingscoords = np.ndarray((len(crossings), 2))
    for j, crossing in enumerate(crossings):
        crossingscoords[j, :] = np.array(nodeshash[crossing])
    plt.scatter(crossingscoords[:, 1], crossingscoords[:, 0], c='black')
    #plt.axis('equal')
    plt.show()

##########################################################
def render_bokeh(nodeshash, ways, crossings):
    nodes = get_nodes_coords_from_hash(nodeshash)

    from bokeh.plotting import figure, show, output_file
    TOOLS="hover,pan,wheel_zoom,reset"
    p = figure(tools=TOOLS)

    # render nodes
    p.scatter(nodes[:, 1], nodes[:, 0], size=10, fill_alpha=0.8,
                        line_color=None)

    # render ways
    for wnodes in ways.values():
        r = lambda: random.randint(0,255)
        waycolor = '#%02X%02X%02X' % (r(),r(),r())
        lats = []; lons = []
        for nodeid in wnodes:
            a, o = nodeshash[nodeid]
            lats.append(a)
            lons.append(o)
        p.line(lons, lats, line_width=2, line_color=waycolor)

    # render crossings
    crossingscoords = np.ndarray((len(crossings), 2))
    for j, crossing in enumerate(crossings):
        crossingscoords[j, :] = np.array(nodeshash[crossing])
    p.scatter(crossingscoords[:, 1], crossingscoords[:, 0], line_color='black')

    output_file("osm-test.html", title="OSM test")

    show(p)  # open a browser
    return

##########################################################
def get_segments(ways, crossings):
    """Get segments, given the ways and the crossings

    Args:
    ways(dict of list): hash of wayid as key and list of nodes as values
    crossings(set): set of nodeids in crossings

    Returns:
    dict of list: hash of segmentid as key and list of nodes as value
    dict of list: hash of nodeid as key and list of sids as value
    """

    segments = {}
    invsegments = {}
    myset = set(crossings)

    sid = 0 # segmentid
    for w, nodes in ways.items():
        if not myset.intersection(set(nodes)): continue
        segment = []
        for node in nodes:
            segment.append(node)

            if node in myset and len(segment) > 1:
                segments[sid] = segment
                for nod in segment:
                    if node in invsegments:
                        invsegments[node].append(sid) 
                    else:
                        invsegments[node] = [sid]
                sid += 1
    debug('Found {} segments'.format(len(segments.keys())))
    return segments, invsegments

##########################################################
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inputosm', help='Input osm file')
    parser.add_argument('--frontend', choices=['bokeh', 'matplotlib'],
                        help='Front end vis')
    parser.add_argument('--verbose', help='verbose', action='store_true')

    args = parser.parse_args()

    args.verbose = True # TODO: remove it

    if args.verbose:
        loglevel = args.verbose if logging.DEBUG else logging.ERROR

    logging.basicConfig(level=loglevel)

    tree = ET.parse(args.inputosm)
    root = tree.getroot() # Tag osm

    ways, invways = get_all_ways(root)
    nodestree, nodeshash = get_all_nodes(root, invways)
    ways, invways = filter_out_orphan_nodes(ways, invways, nodeshash)
    crossings = get_crossings(invways)
    segments, invsegments = get_segments(ways, crossings)
    #render_map(nodeshash, ways, crossings, args.frontend)
    render_map(nodeshash, segments, crossings, args.frontend)
    
##########################################################
if __name__ == '__main__':
    main()

