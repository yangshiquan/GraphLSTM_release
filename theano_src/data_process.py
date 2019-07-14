#!/usr/bin/python 
# -*- coding: utf-8 -*-

import codecs as cs
import random
import re, sys, os
import numpy
import theano
from collections import defaultdict
from .edmonds_mst import * #edmonds import mst

OOV = '_OOV_'
SEG = 'Segmentation'
feature_thresh = 0
name_len_thresh = 5


# Dirty statstics for single sentence results, copy this func from lstm_RE.py
def eval_logitReg_accuracy(predictions, goldens):
    assert len(predictions) == len(goldens)
    correct = 0.0
    for p, g in zip(predictions, goldens):
        #print 'in eval_logitReg_accuracy,', p, g
        if p == g:
            correct += 1.0
    return correct/len(predictions)

# Generate annotations that contains article id, entity names and sentence length
def quick_gen_anno_from_json(infile, outfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf:
        for line in inf:
            content = json.loads(line) #, encoding='utf-8')
            for item in content:
                local_map = {}
                sentences = item['sentences']
                pmid = item['article']
                entities = item['entities']
                relation = item['relationLabel']
                entity_arry = [pmid, str(len(sentences))]
                for entity in entities:
                    if 'indices' not in entity or len(entity['indices']) == 0 :
                        sys.stderr.write('WARNING: entity mention '+entity['mention'].encode('utf-8')+' does not have index!\n')
                    entity_arry.append(entity['type']+':'+entity['id'])
                outf.write('\t'.join(entity_arry)+'\n')


# Sample high-confident examples for the PubMed scale extraction
def sample_high_conf_predictions_PubMed(sent_file, pred_file, anno_file, num_samples):
    all_instances = load_high_conf_predictions(sent_file, anno_file, pred_file)
    for i, ins in enumerate(random.sample(all_instances, int(num_samples))):
        print ('\n'.join(gen_html_for_ins(ins, i)))


def statistics_open_extraction(sent_file, anno_file, pred_file, thresh):
    all_instances = load_high_conf_predictions(sent_file, anno_file, pred_file, float(thresh)) 
    single_sent_set = set()
    multi_sent_set = set()
    multi_drug_set = set()
    multi_gene_set = set()
    multi_variant_set = set()
    single_drug_set = set()
    single_gene_set = set()
    single_variant_set = set()
    for ins in all_instances:
        anno = ins[1].split('\t')
        multi_sent_set.add(tuple(anno[2:]))
        multi_drug_set.add(anno[2])
        multi_gene_set.add(anno[3])
        if len(anno) > 4:
            multi_variant_set.add(anno[4])
        if int(anno[1]) == 1:
            single_sent_set.add(tuple(anno[2:]))
            single_drug_set.add(anno[2])
            single_gene_set.add(anno[3])
            if len(anno) > 4:
                single_variant_set.add(anno[4])
    print ('high confident instances numbers:', thresh, len(single_sent_set), len(multi_sent_set))
    print ('single sentence distinct entities:', len(single_drug_set), len(single_gene_set), len(single_variant_set))
    print ('multi-sentence distinct entities:', len(multi_drug_set), len(multi_gene_set), len(multi_variant_set))

# Sample high-confident examples
def sample_high_conf_predictions(sent_dir, pred_dir, num_folds, sent_file_name, anno_file_name, pred_file_prefix, thresh, num_samples):
    all_instances = []
    accuracies = []
    for i in range(int(num_folds)):
        sentence_file = os.path.join(sent_dir, str(i), sent_file_name)
        annotation_file = os.path.join(sent_dir, str(i), anno_file_name)
        pred_file = os.path.join(pred_dir, pred_file_prefix+str(i)+'.predictions')
        #all_instances.extend(load_high_conf_predictions(sentence_file, annotation_file, pred_file, float(thresh)))
        all_instances = load_high_conf_predictions(sentence_file, annotation_file, pred_file, float(thresh))
    #for i, ins in enumerate(random.sample(all_instances, int(num_samples))):
    #    print '\n'.join(gen_html_for_ins(ins, i))
        pred_array = []
        gold_array = []
        for ins in all_instances:
            if ins[1].split('\t')[1] != '1':
                continue
            if float(ins[0].split('\t')[-1]) > 0.5:
                pred_array.append(1)
            else:
                pred_array.append(0)
            if ins[2].split('\t')[-1] == 'None':
                gold_array.append(0)
            else:
                gold_array.append(1)
        print (len(pred_array), len(gold_array))
        accuracies.append(eval_logitReg_accuracy(pred_array, gold_array))
    print (numpy.mean(accuracies))


def gen_html_for_ins(instance, num):
    content_arry = ['<div class=\'row\'><div class=\'col-md-12\'><div class=\'page-header\'>']
    content_arry.append('<h1> ('+str(num)+') '+instance[1]+' </h1></div>')
    content_arry.append('<div>p = '+instance[0].split('\t')[1]+'</div>')
    content_arry.append('<div class=\'panel panel-default\'><div class=\'panel-body\'><ul>')
    content_arry.append('<li>')
    content_arry.append(instance[2].split('\t')[0]+'</li>')
    content_arry.append('</ul></div></div>')
    content_arry.append('<hr></div></div>')
    return content_arry

def load_high_conf_predictions(sentence_file, annotation_file, pred_file, thresh=0.5):
    instances = []
    single_sent_anno_set = set()
    multi_sent_anno_set = set()
    with open(sentence_file) as stf, open(annotation_file) as anf, open(pred_file) as pf:
        for sl, al, pl in zip(stf, anf, pf):
            anno = al.strip().split('\t')
            multi_sent_anno_set.add(tuple(anno[2:]))
            if int(anno[1]) == 1:
                single_sent_anno_set.add(tuple(anno[2:]))
            if float(pl.strip().split('\t')[-1]) > thresh:
                instances.append([pl.strip(), al.strip(), sl.strip()])
    #for rel in single_sent_anno_set:
    #    print rel
    print ('total distinct candidates for single sentence:', len(single_sent_anno_set), 'multiple sentences:', len(multi_sent_anno_set))
    return instances

# Generate chain-structure for the tree-LSTM implementation
def quick_chain(sentfile, outdepfile):
    with open(sentfile) as sf, open(outdepfile, 'w') as odf:
        for line in sf:
            content = line.strip().split('\t')[0]
            dummy_dep = [(i+1) for i in range(len(content.lower().split(' ')))]
            dummy_dep[-1] = -1
            odf.write(' '.join(map(str,dummy_dep))+'\n')


# Sample the pos/neg examples to be similar size as the other.
def quick_sample(sentfile, depfile):
    with open(sentfile) as sf, open(depfile) as df, open(sentfile+'.balanced', 'w') as osf, open(depfile+'.balanced', 'w') as odf:
        contents = []
        deplabels = []
        line_count = 0
        pos = []
        neg = []
        while True:
            sent_line = sf.readline()
            contents.append(sent_line)
            if not sent_line:
                assert not df.readline()
                break
            deplabels.append(df.readline())
            elems = sent_line.strip().split('\t')
            if elems[-1] == '+':
                pos.append(line_count)
            else:
                neg.append(line_count)
            line_count += 1
        size = len(neg)
        pos_new = random.sample(pos, size)
        for p, n in zip(pos_new, neg):
            print (p, n)
            osf.write(contents[p])
            osf.write(contents[n])
            odf.write(deplabels[p])
            odf.write(deplabels[n])


# A quick check on how many dev instances are in the training instances.
def quick_check(train_file, dev_file):
    train = load_text(train_file)
    dev = load_text(dev_file)
    train_set = set(train)
    count = 0
    print (train[0])
    print (dev[0])
    for line in dev:
        if line in train_set:
            count += 1
    print (count)

def load_text(filename):
    content = []
    with open(filename) as inf:
        for line in inf:
            #print line.split('\t')[0]
            content.append(line.strip().split('\t')[0])
    print (len(content))
    return content

# generate path and remove circle
def gen_path(path_dict):
    start = path_dict['from']
    end = path_dict['to']
    path_info = path_dict['steps']
    path = []
    pre, prepre = -1, -1
    for i, item in enumerate(path_info):
        if item['from'] == -1:
            assert i == 0
            item['from'] = start
        if item['to'] == -1:
            assert i == len(path_info)-1
            item['to'] = end
        if len(path) > 0 and path[-1][0] == item['to']:
            path.pop()
            continue
        if len(path) > 0:
            assert path[-1][1] == item['from']
        path.append((item['from'], item['to'], item['label']))
    #print 'path!! type:', path_dict['name'], start, end, path
    return path


def gen_graph_from_paths(paths):
    path_graph = dict()
    node_pair_set = set()
    print ('generate graph!!!')
    for path in paths:
        for node in path:
            pair = (node[0], node[1])
            if pair in node_pair_set:
                assert (node[1], node[0]) in node_pair_set
                continue
            node_pair_set.add(pair)
            node_pair_set.add((node[1], node[0]))
            if node[0] not in path_graph:
                path_graph[node[0]] = []
            value = (node[1], node[2])
            if value not in path_graph[node[0]]:
                path_graph[node[0]].append(value)
        print (path_graph)
    return path_graph


def topolgical_sort(graph_unsorted):
    """
    Repeatedly go through all of the nodes in the graph, moving each of
    the nodes that has all its edges resolved, onto a sequence that
    forms our sorted graph. A node has all of its edges resolved and
    can be moved once all the nodes its edges point to, have been moved
    from the unsorted graph onto the sorted one.
    """

    # This is the list we'll return, that stores each node/edges pair
    # in topological order.
    graph_sorted = []
    # Convert the unsorted graph into a hash table. This gives us
    # constant-time lookup for checking if edges are unresolved, and
    # for removing nodes from the unsorted graph.

    # Run until the unsorted graph is empty.
    while graph_unsorted:
        # Go through each of the node/edges pairs in the unsorted
        # graph. If a set of edges doesn't contain any nodes that
        # haven't been resolved, that is, that are still in the
        # unsorted graph, remove the pair from the unsorted graph,
        # and append it to the sorted graph. Note here that by using
        # using the items() method for iterating, a copy of the
        # unsorted graph is used, allowing us to modify the unsorted
        # graph as we move through it. We also keep a flag for
        # checking that that graph is acyclic, which is true if any
        # nodes are resolved during each pass through the graph. If
        # not, we need to bail out as the graph therefore can't be
        # sorted.
        acyclic = False
        sorted_nodes = set()
        for node, edges in graph_unsorted.items():
            print ('processing node:', node, edges)
            for edge, label in edges:
                print ('processing edge:', node, edge)
                if edge in graph_unsorted:
                    break
            else:
                acyclic = True
                del graph_unsorted[node]
                graph_sorted.append((node, edges))
                sorted_nodes.add(node)
                print ('graph_sorted:', graph_sorted)
        if not acyclic:
            # Uh oh, we've passed through all the unsorted nodes and
            # weren't able to resolve any of them, which means there
            # are nodes with cyclic edges that will never be resolved,
            # so we bail out with an error.
            raise RuntimeError("A cyclic dependency occurred")
            '''print 'A cyclic dependency occurred'
            for node, edges in graph_unsorted.items():
                print 'processing node:', node, edges
                removed_edge = False
                for edge, label in edges:
                    if edge in sorted_nodes:
                        graph_unsorted[node].remove((edge, label))
                        removed_edge = True
                        break
                if removed_edge:
                    break
            '''
    return graph_sorted


def gen_chain_shortest_paths(infile, outfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf:
        ignored_item = 0
        for line in inf:
            content = json.loads(line) #, encoding='utf-8')
            for item in content:
                local_map = {}
                sentences = item['sentences']
                entities = item['entities']
                relation = item['relationLabel']
                paths = item['paths']
                origin_text = []
                dep_arcs = []
                pre_root = -1
                #print 'a new instance!!'
                # Get the original text
                for sentence in sentences:
                    #print 'sentence root:', root
                    for node in sentence['nodes']:
                        origin_text.append(re.sub('[ \t]', '', node['label'].strip()))
                indices = []
                # Substitute the Entities to special symbols
                # Double check the entity indices at the same time.
                for entity in entities:
                    if 'indices' not in entity or len(entity['indices']) == 0 :
                        sys.stderr.write('WARNING: entity mention '+entity['mention'].encode('utf-8')+' does not have index!\n')
                        indices.append([0])
                        continue
                    indices.append(entity['indices'])
                    start = entity['indices'][0]
                    end = entity['indices'][-1] + 1
                    try:
                        assert entity['mention'] in ' '.join(origin_text[start:end]).strip()
                    except:
                        sys.stderr.write('WARNING: entity mention does not match! '+entity['mention'].encode('utf-8')+' v.s. '+' '.join(origin_text[start:end]).encode('utf-8') +'\n')
                        sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + ', Sentences:')
                        for sentence in sentences:
                            sys.stderr.write(' Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+',')
                        sys.stderr.write('\n')
                        sys.stderr.write('Original Text: '+' '.join(origin_text).encode('utf-8')+'\n')
                        sys.stderr.write('Original entity indices: ' + str(entity['indices']).encode('utf-8') + '\t Converted indices: '+ str(range(start, end)) + '\n')
                    for eidx in range(start, end):
                        origin_text[eidx] = '<ANNO_TYPE_'+entity['type']+'>'
                # Get the paths, construct the directed graph and run a topological sort.
                '''path_array = []
                pre_name = ''
                for path in paths:
                    path_name = path['name']
                    if path_name.startswith('drug_'):
                        if path_name == pre_name and path['to'] != path_array[-1][-1][1]
                        path_array.append(gen_path(path))
                path_graph = gen_graph_from_paths(path_array)
                print path_graph
                print topolgical_sort(path_graph)
                ''' 
                if len(paths) == 0:
                    print ('no path!!!')
                    ignored_item += 1
                    continue
                path = gen_path(paths[0])
                clean_path = [item[0] for item in path]
                clean_path.append(path[-1][1])
                assert len(indices) == 2
                #print indices[0], clean_path[0]
                #print indices[-1], clean_path[-1]
                assert clean_path[0] in indices[0]
                assert clean_path[-1] in indices[-1]
                # augment the first entity
                for idx in indices[0]:
                    if idx not in clean_path:
                        clean_path.insert(0, idx)
                # augment the last entity
                for idx in indices[-1]:
                    if idx not in clean_path:
                        clean_path.append(idx)
                outf.write(re.sub('\t', ' ', ' '.join(map(lambda x: origin_text[x], clean_path)))+'\t'+'\t'.join([' '.join(map(str, map(lambda x: clean_path.index(x),idx))) for idx in indices])+'\t'+relation+'\n')
                #grf.write(' '.join(dep_arcs)+'\n')
        print ('Ignored', ignored_item, 'items!')

def filter_sentence_json(infile, outfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf:
        total_ins = 0
        single_sent = 0
        filtered_array = []
        for line in inf:
            content = json.loads(line) #, encoding='utf-8')
            for item in content:
                sentences = item['sentences']
                total_ins += 1
                if len(sentences) == 1:
                    single_sent += 1
                    filtered_array.append(item)
        outf.write(numpy.unicode(json.dumps(filtered_array, ensure_ascii=False)))
        print ('total instances = ', total_ins, 'single sentence instances = ', single_sent)

def gen_graph_from_json(infile, outfile, graphfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf, cs.open(graphfile, 'w', encoding='utf-8') as grf:
        for line in inf:
            content = json.loads(line) #, encoding='utf-8')
            for item in content:
                local_map = {}
                sentences = item['sentences']
                entities = item['entities']
                relation = item['relationLabel']
                origin_text = []
                dep_arcs = []
                pre_root = -1
                #print 'a new instance!!'
                for sentence in sentences:
                    root = sentence['root']
                    #print 'sentence root:', root
                    for node in sentence['nodes']:
                        origin_text.append(re.sub('[ \t]', '', node['label'].strip()))
                        arc_list = node['arcs']
                        node_idx = node['index']#-prev_sent_length
                        arcs = []
                        for arc in arc_list:
                            try:
                                assert arc['toIndex'] != node['index']
                                arcs.append(re.sub(' ', '_', arc['label'])+'::'+str(arc['toIndex']))
                                #arc_map[arc['toIndex']-prev_sent_length] = 1
                            except:
                                sys.stderr.write('arc point to self!!!! Node:'+str(node['index'])+','+node['label']+'\t'+str(arc_list)+'. Printing out the \n')
                                sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + 
                                        ', Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+', paraSent:'+str(sentence['paragraphSentence'])+'\n')
                                for node in sentence['nodes']:
                                    sys.stderr.write(node['label']+'\t'+str(node['arcs'])+'\n')
                                #if temp_to not in arc_map:
                                #    arc_map[temp_to] = 100
                        dep_arcs.append(',,,'.join(arcs))
                    try:
                        assert root > -1
                    except:
                        root = 0
                        sys.stderr.write('Sentence NO ROOT! ===== Instance information: PMID: '+str(item['article']) + 
                                ', Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+'\n')
                    #print 'root deps:', dep_arcs[root]
                    if pre_root != -1:
                        dep_arcs[pre_root] += ',,,nextsent:next::'+str(root)
                        dep_arcs[root] += ',,,prevsent:prev::'+str(pre_root)
                    pre_root = root
                assert len(dep_arcs) == len(origin_text) #len(text)
                indices = []
                for entity in entities:
                    if 'indices' not in entity or len(entity['indices']) == 0 :
                        sys.stderr.write('WARNING: entity mention '+entity['mention'].encode('utf-8')+' does not have index!\n')
                        indices.append([0])
                        continue
                    indices.append(entity['indices'])
                    start = entity['indices'][0]
                    end = entity['indices'][-1] + 1
                    try:
                        assert entity['mention'] in ' '.join(origin_text[start:end]).strip()
                    except:
                        sys.stderr.write('WARNING: entity mention does not match! '+entity['mention'].encode('utf-8')+' v.s. '+' '.join(origin_text[start:end]).encode('utf-8') +'\n')
                        sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + ', Sentences:')
                        for sentence in sentences:
                            sys.stderr.write(' Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+',')
                        sys.stderr.write('\n')
                        sys.stderr.write('Original Text: '+' '.join(origin_text).encode('utf-8')+'\n')
                        sys.stderr.write('Original entity indices: ' + str(entity['indices']).encode('utf-8') + '\t Converted indices: '+ str(range(start, end)) + '\n')
                    for eidx in range(start, end):
                        # Note: change this line to get or remove the entity name.
                        origin_text[eidx] += '<ANNO_TYPE_'+entity['type']+'>'
                outf.write(re.sub('\t', ' ', ' '.join(origin_text))+'\t'+'\t'.join([' '.join(map(str,idx)) for idx in indices])+'\t'+relation+'\n')
                grf.write(' '.join(dep_arcs)+'\n')

# helper function for revert sentence such that bi-directional LSTM can capture semantic order.
def reverse_sent(indices, dep_arcs):
    sent_len = len(dep_arcs)
    new_indices = [[sent_len-1-i for i in idx] for idx in indices]
    new_deps = [',,,'.join(map(lambda x: '::'.join([str(sent_len-1-int(x[0])), x[1]]), [arc.split('::') for arc in item.split(',,,')])) for item in dep_arcs]
    return new_indices, new_deps


def gen_MST_from_json(infile, outfile, depfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf, cs.open(depfile, 'w', encoding='utf-8') as depf:
        for line in inf:
            content = json.loads(line) #, encoding='utf-8')
            #print len(content)
            count = 0
            for item in content:
                local_map = {}
                sentences = item['sentences']
                entities = item['entities']
                relation = item['relationLabel']
                origin_text = []
                dep_arcs = []
                #prev_sent_length = 0
                pre_root = -1
                for sentence in sentences:
                    dep_graph = [] #dict()
                    root = sentence['root']
                    for node in sentence['nodes']:
                        origin_text.append(node['label'])
                        arc_list = node['arcs']
                        node_idx = node['index']#-prev_sent_length
                        for arc in arc_list:
                            if arc['label'].startswith('deparc'):
                                try:
                                    assert arc['toIndex'] != node['index']
                                    dep_graph.append(Arc(arc['toIndex'], 1, node_idx))
                                    #arc_map[arc['toIndex']-prev_sent_length] = 1
                                except:
                                    sys.stderr.write('dependency arc point to self!!!! Node:'+str(node['index'])+','+node['label']+'\t'+str(arc_list)+'. Printing out the \n')
                                    sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + 
                                            ', Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+', paraSent:'+str(sentence['paragraphSentence'])+'\n')
                                    for node in sentence['nodes']:
                                        sys.stderr.write(node['label']+'\t'+str(node['arcs'])+'\n')
                            elif arc['label'].startswith('adjtok'):
                                temp_to = arc['toIndex']
                                dep_graph.append(Arc(temp_to, 100, node_idx))
                    try:
                        assert root > -1
                    except:
                        root = 0
                        sys.stderr.write('Sentence NO ROOT! ===== Instance information: PMID: '+str(item['article']) + 
                                ', Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+'\n')
                    tree = min_spanning_arborescence(dep_graph, root) #mst(root-prev_sent_length, dep_graph)
                    temp_dep_tree = [0] * (len(tree)+1)
                    dep_arcs.extend(temp_dep_tree)
                    for k in tree:
                        dep_arcs[k] = tree[k].head
                    assert dep_arcs[root] == 0 #prev_sent_length
                    dep_arcs[root] = -1
                    #prev_sent_length += len(dep_graph)
                    if pre_root != -1:
                        dep_arcs[pre_root] = root
                    pre_root = root
                assert len(dep_arcs) == len(origin_text) #len(text)
                indices = []
                for entity in entities:
                    if 'indices' not in entity or len(entity['indices']) == 0 :
                        sys.stderr.write('WARNING: entity mention '+entity['mention'].encode('utf-8')+' does not have index!\n')
                        indices.append([0])
                        continue
                    indices.append(entity['indices'])
                    start = entity['indices'][0]
                    end = entity['indices'][-1] + 1
                    try:
                        assert entity['mention'] in ' '.join(origin_text[start:end]).strip()
                    except:
                        sys.stderr.write('WARNING: entity mention does not match! '+entity['mention'].encode('utf-8')+' v.s. '+' '.join(origin_text[start:end]).encode('utf-8') +'\n')
                        sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + ', Sentences:')
                        for sentence in sentences:
                            sys.stderr.write(' Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+',')
                        sys.stderr.write('\n')
                        sys.stderr.write('Original Text: '+' '.join(origin_text).encode('utf-8')+'\n')
                        sys.stderr.write('Original entity indices: ' + str(entity['indices']).encode('utf-8') + '\t Converted indices: '+ str(range(start, end)) + '\n')
                    for eidx in range(start, end):
                        origin_text[eidx] = '<ANNO_TYPE_'+entity['type']+'>'
                outf.write(re.sub('\t', ' ', ' '.join(origin_text))+'\t'+'\t'.join([' '.join(map(str,idx)) for idx in indices])+'\t'+relation+'\n')
                depf.write(' '.join(map(str, [a if a not in local_map else local_map[a] for a in dep_arcs ]))+'\n')
                count += 1


''' Stale version of tree construction using heurestics. Changing to MST version'''
def gen_data_from_json(infile, outfile, depfile):
    import json
    with  open(infile) as inf, cs.open(outfile, 'w', encoding='utf-8') as outf, cs.open(depfile, 'w', encoding='utf-8') as depf:
        count = 1
        for line in inf:
            sys.stderr.write('processing line '+str(count) + '\n')
            content = json.loads(line) #, encoding='utf-8')
            #print len(content)
            icount = 0
            for item in content:
                local_map = {}
                missing_count = 0
                sentences = item['sentences']
                entities = item['entities']
                relation = item['relationLabel']
                text = []
                dep_arcs = []
                origin_text = []
                origin_dep = []
                for sentence in sentences:
                    for node in sentence['nodes']:
                        origin_text.append(node['label'])
                        origin_dep.append(node['arcs'])
                        arc_list = node['arcs']
                        for arc in arc_list:
                            if arc['label'].startswith('depinv'):
                                dep_arcs.append(arc['toIndex'])
                                text.append(node['label'])
                                break
                        try:
                            assert (arc['label'].startswith('depinv') or node['index'] == sentence['root'])
                        except:
                            #print arc_list
                            missing_count += 1
                            if node['index'] < len(sentence['nodes'])-1:
                                dep_arcs.append(node['index']+1)
                            else:
                                dep_arcs.append(node['index']-1)
                            #print node['index'], sentence['root']
                        if node['index'] == sentence['root']:
                            if arc['label'].startswith('depinv'):
                                dep_arcs[-1] = -1
                            else:
                                dep_arcs.append(-1)
                                text.append(node['label'])
                        local_map[node['index']] = node['index'] - missing_count
                assert len(dep_arcs) == len(origin_text) #len(text)
                indices = []
                for entity in entities:
                    if 'indices' not in entity or len(entity['indices']) == 0 :
                        sys.stderr.write('WARNING: entity mention '+entity['mention'].encode('utf-8')+' does not have index!\n')
                        indices.append([0])
                        continue
                    indices.append(entity['indices'])
                    start = entity['indices'][0]
                    end = entity['indices'][-1] + 1
                    try:
                        assert entity['mention'] in ' '.join(origin_text[start:end]).strip()
                        #assert entity['mention'] in ' '.join(text[start:end]).strip()
                    except:
                        sys.stderr.write('WARNING: entity mention does not match! '+entity['mention'].encode('utf-8')+' v.s. '+' '.join(origin_text[start:end]).encode('utf-8') +'\n')
                        sys.stderr.write('===== Instance information: PMID: '+str(item['article']) + ', Sentences:')
                        for sentence in sentences:
                            sys.stderr.write(' Paragraph '+str(sentence['paragraph'])+', sentence '+str(sentence['sentence'])+',')
                        sys.stderr.write('\n')
                        sys.stderr.write('Collapsed Text: '+' '.join(text).encode('utf-8')+'\n')
                        sys.stderr.write('Original Text: '+' '.join(origin_text).encode('utf-8')+'\n')
                        sys.stderr.write('Original entity indices: ' + str(entity['indices']).encode('utf-8') + '\t Converted indices: '+ str(range(start, end)) + '\n')
                        sys.stderr.write('The original sentence with dependency arcs:\n')
                        for t, a in zip(origin_text, origin_dep):
                            sys.stderr.write(t.encode('utf-8')+'\t'+str(a).encode('utf-8')+'\n')
                outf.write(re.sub('\t', ' ', ' '.join(origin_text))+'\t'+'\t'.join([' '.join(map(str,idx)) for idx in indices])+'\t'+relation+'\n')
                depf.write(' '.join(map(str, [a if a not in local_map else local_map[a] for a in dep_arcs ]))+'\n')
                icount += 1
            sys.stderr.write('instances in line '+str(count)+': ' +str(icount) + '\n')
            count += 1


def quick_split(infile, fold):
    with open(infile) as inf:
        content = []
        for line in inf:
            content.append(line)
        beam = len(content) / fold
        random.shuffle(content) 
        for i in range(fold):
            with open(infile+'_split_'+str(i)+'.train', 'w') as trainf, open(infile+'_split_'+str(i)+'.test', 'w') as testf:
                for line in content[0:i*beam]:
                    trainf.write(line)
                for line in content[i*beam: (i+1)*beam]:
                    testf.write(line)
                for line in content[(i+1)*beam:]:
                    trainf.write(line)


def prepare_data(seqs, eidxs, mask=None, maxlen=None):
    """Create the matrices from the datasets.

    This pad each sequence to the same lenght: the lenght of the
    longuest sequence or maxlen.

    if maxlen is set, we will cut all sequence to this maximum
    lenght.

    This swap the axis!
    """
    # x: a list of sentences
    lengths = [len(s) for s in seqs]

    # This part: suspeciously wrong.
    if maxlen is not None:
        new_seqs = []
        new_lengths = []
        for l, s in zip(lengths, seqs):
            if l < maxlen:
                new_seqs.append(s)
                new_lengths.append(l)
            else:
                new_seqs.append(s[:maxlen])
                new_lengths.append(maxlen)
        lengths = new_lengths
        seqs = new_seqs

        if len(lengths) < 1:
            return None, None, None

    n_samples = len(seqs)
    maxlen = numpy.max(lengths)
    assert seqs[0].ndim == 2
    x = numpy.zeros((maxlen, n_samples, seqs[0].shape[1])).astype('int32')
    if mask is not None:
        x_mask = numpy.zeros((maxlen, n_samples, maxlen, mask[0].shape[-1])).astype(theano.config.floatX)
    else:
        x_mask = numpy.zeros((maxlen, n_samples)).astype(theano.config.floatX)
    num_entities = len(eidxs[0])
    np_eidxs = [numpy.zeros((maxlen, n_samples)).astype(theano.config.floatX) for i in range(num_entities)]
    for idx, s in enumerate(seqs):
        x[:lengths[idx], idx, :] = s
        if mask is not None:
            x_mask[:lengths[idx], idx, :lengths[idx], :] = mask[idx][:lengths[idx], :lengths[idx], :]
        else:
            x_mask[:lengths[idx], idx] = 1.
        for i in range(num_entities):
            if numpy.all(numpy.array(eidxs[idx][i]) < maxlen ): 
                np_eidxs[i][eidxs[idx][i], idx] = 1.
            else:
                np_eidxs[i][maxlen-1, idx] = 1.
    return x, x_mask, np_eidxs


def check_entity(x, idx):
    for i, (ins, ii) in enumerate(zip(x, idx)):
        sent_len = len(ins)
        for item in ii:
            for li in item:
                assert li < sent_len
                try:
                    assert ins[li].startswith('<anno_type')
                except:
                    pass

def read_graph_dependencies(graph_file, arc_type_dict, fine_grain=True):
    dep_graphs = []
    if 'adjtok' not in arc_type_dict:
        arc_type_dict['adjtok'] = 0
    with open(graph_file, 'r') as parents_f:
        while True:
            cur_parents = parents_f.readline()
            if not cur_parents :
                break
            cur_deps = [[elem.split('::') for elem in p.split(',,,')] for p in cur_parents.strip().split(' ')]
            for p in cur_parents.strip().split(' '):
                for elem in p.split(',,,'):
                    temp = elem.split('::')
                    try:
                        assert len(temp) == 2
                    except:
                        print (elem, p)
            dep_graphs.append(construct_graph_deps(cur_deps, arc_type_dict, fine_grain))
    return dep_graphs, arc_type_dict 

# get a dict of the arc_types and dependencies with types
def construct_graph_deps(dep_array, arc_type_dict, fine_grain=True):
    dep_graph = []
    ignore_types = ['prevsent', 'coref', 'discSenseInv', 'adjsent', 'discSense', 'nextsent', 'depsent', 'discExplicitInv', 'discExplicit', 'depinv']
    focus_types = ['deparc'] #, 'depinv']
    for i, elem in enumerate(dep_array):
        local_dep = []
        for pair in elem:
            arc_type = pair[0].split(':')[0]
            if fine_grain and arc_type in focus_types:
                arc_type = pair[0][:11]
            dep_node = int(pair[1])
            if dep_node < 0 or arc_type in ignore_types: # or arc_type == 'deparc' or arc_type == 'depinv':   
                continue
            # I modified this to support bi-direction
            if dep_node != i:
                if arc_type not in arc_type_dict:
                    arc_type_dict[arc_type] = len(arc_type_dict) 
                local_dep.append((dep_node, arc_type_dict[arc_type]))
        try:
            assert (len(local_dep) > 0 or i == 0)
        except:
            #print i, elem
            pass
        dep_graph.append(local_dep)
    return dep_graph

# prepare input for the type-multiply strategy (each type has its own parameters)
def gen_child_mask_from_dep(dependency, num_arc_type):
    sent_len = len(dependency)
    child_exist = numpy.zeros([sent_len, sent_len, num_arc_type]).astype(theano.config.floatX) 
    for ii, elem in enumerate(dependency):
        if ii != 0:
            child_exist[ii, ii-1, 0] = 1
            # Here I add the below line to support bi-direction
        if ii != sent_len - 1:
            child_exist[ii, ii+1, 0] = 1
        for jj, el in enumerate(elem):
            child_exist[ii, el[0], el[1]] = 1
    return child_exist

# prepare input for the type-add strategy (dependency concatenate with type, and add them together in hidden-to-hidden transformation)
def gen_child_mask_from_dep_add(dependency, num_arc_type):
    sent_len = len(dependency)
    child_exist = numpy.zeros([sent_len, sent_len, 2]).astype(theano.config.floatX) 
    for ii, elem in enumerate(dependency):
        if ii != 0:
            child_exist[ii, ii-1, 0] = 1
            child_exist[ii, ii-1, 1] = 0#1
            # Here I add the below line to support bi-direction
        if ii != sent_len - 1:
            child_exist[ii, ii+1, 0] = 1
            child_exist[ii, ii+1, 1] = 0#1
        for jj, el in enumerate(elem):
            child_exist[ii, el[0], 0] = 1
            child_exist[ii, el[0], 1] = el[1]#+1
    assert numpy.all(child_exist[:,:,0] <= 1.)
    assert numpy.all(child_exist[:,:,1] < num_arc_type)
    return child_exist


def collect_data(corpus_x, corpus_y, corpus_idx, corpus_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add):
    corpus_x.extend( [[words2idx.get(w, 0) for w in sent]  for sent in x] )
    corpus_y.extend(y)
    corpus_idx.extend(idx)
    if dep:
        if add:
            child_exists = [gen_child_mask_from_dep_add(dependency, len(arc_type_dict)) for dependency in dependencies]
        else:
            child_exists = [gen_child_mask_from_dep(dependency, len(arc_type_dict)) for dependency in dependencies]
        for i, (a,b,dep) in enumerate(zip(x, child_exists, dependencies)):
            assert len(a) == len(b)
        corpus_dep.extend(child_exists)
        assert len(corpus_idx) == len(corpus_dep)
    assert len(corpus_x) == len(corpus_y)
    assert len(corpus_y) == len(corpus_idx)


def load_data_cv(data_dir, folds, dev_fold, test_fold=None, arc_type_dict=dict(), num_entities=2, dep=False, content_fname='sentences', dep_fname='graph_arcs', add=True):
    corpus = []
    for i in range(folds):
        sub_corpus = read_file(os.path.join(data_dir, str(i), content_fname), num_entities)
        if dep:
            dependencies, arc_type_dict = read_graph_dependencies(os.path.join(data_dir, str(i), dep_fname), arc_type_dict, add)
            corpus.append((sub_corpus, dependencies))
        else:
            corpus.append((sub_corpus, None))

    # get word dict
    words = [w for sub_corpus, _ in corpus for sent in sub_corpus[0] for w in sent ]
    words2idx = {OOV: 0}
    for w in words:
        if w not in words2idx:
            words2idx[w] = len(words2idx)    
    print ('voc_size:', len(words2idx))
    if dep:
        print ('arc_type_dict:', len(arc_type_dict), arc_type_dict)
    train_set_x, train_set_y, train_set_idx = [], [], [] 
    valid_set_x, valid_set_y, valid_set_idx = [], [], []
    test_set_x, test_set_y, test_set_idx = [], [], []
    
    if dep:
        train_set_dep = []
        valid_set_dep = []
        test_set_dep = []
        print ('load dependencies as well!!!')
    else:
        train_set_dep, valid_set_dep, test_set_dep = None, None, None
    for i, (sub_corpus, dependencies) in enumerate(corpus):
        x, y, idx = sub_corpus
        print ('check entity of subcorpus', i)
        check_entity(x, idx)
        if i == dev_fold:
            collect_data(valid_set_x, valid_set_y, valid_set_idx, valid_set_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add)
        if test_fold is not None and i == test_fold:
            collect_data(test_set_x, test_set_y, test_set_idx, test_set_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add)
        elif i != dev_fold:
            collect_data(train_set_x, train_set_y, train_set_idx, train_set_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add)
    print ('after word to index, sizes:', len(train_set_x), len(valid_set_x), len(test_set_x) if test_fold is not None else 0)
    print ('arc_type_dict:', len(arc_type_dict) )
    train = [train_set_x, train_set_y, train_set_idx]
    valid = [valid_set_x, valid_set_y, valid_set_idx]
    if test_fold is not None:
        test = [test_set_x, test_set_y, test_set_idx]
    if dep:
        train.append(train_set_dep)
        valid.append(valid_set_dep)
        if test_fold is not None:
            test.append(test_set_dep)
    else:
        train.append(None)
        valid.append(None)
        if test_fold is not None:
            test.append(None)
    labels2idx = {'+':1, '-':0}
    dics = {'words2idx': words2idx, 'labels2idx': labels2idx}
    if dep:
        dics['arcs2idx'] = arc_type_dict
    if test_fold is not None:
        return [train, valid, test, dics]
    return [train, valid, dics]



def read_file(filename, num_entities=2, labeled=True):
    corpus_x = []
    corpus_y = []
    corpus_idx = []
#        urlStr = 'http[s]?://(?:[a-zA-Z]|[1-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    with cs.open(filename, 'r', encoding='utf-8') as inf:
        line_count = 0
        for line in inf:
            line_count += 1
            line = line.strip()
            if len(line) == 0:
                continue
            #sentence, entity_ids_1, entity_ids_2, label = line.split('\t') 
            elems = line.split('\t') 
            entity_id_arry = []
            for ett in elems[1:1+num_entities]:
                entity_id = map(int, ett.split(' '))
                entity_id_arry.append(entity_id)
            assert len(entity_id_arry) == num_entities
            assert len(elems) == num_entities + 2
            x = elems[0].lower().split(' ')
            label = elems[-1]
            try:
                for i in range(num_entities):
                    assert entity_id_arry[i][-1] < len(x)
            except:
                sys.stderr.write('abnormal entity ids:'+str(entity_id_arry)+', sentence length:'+str(len(x))+'\n')
                continue
            #sentence = stringQ2B(sentence)
            if len(x) < 1:
                print (x)
                continue
            if label == 'None':
                y = 0
            else:
                y = 1
            corpus_x.append(x)
            corpus_y.append(y)
            corpus_idx.append(entity_id_arry)
    print ('read file', filename, len(corpus_x), len(corpus_y), len(corpus_idx))
    return corpus_x, corpus_y, corpus_idx 



def load_data(train_path=None, valid_path=None, test_path=None, num_entities=2, dep=False, train_dep=None, valid_dep=None, test_dep=None, add=True):
    print ('loading training data from', train_path, 'loading valid data from', valid_path, 'loading test data from', test_path)
    corpus = []
    arc_type_dict = dict()
    # load training data
    #train_corpus = read_file(os.path.join(train_path, content_fname+'.train'), num_entities)
    train_corpus = read_file(train_path, num_entities)
    if dep:
        assert train_dep is not None
        dependencies, arc_type_dict = read_graph_dependencies(train_dep, arc_type_dict, add)
        corpus.append((train_corpus, dependencies))
    else:
        corpus.append((train_corpus, None))
    # load dev data
    dev_corpus = read_file(valid_path, num_entities)
    if dep:
        assert valid_dep is not None
        dependencies, arc_type_dict = read_graph_dependencies(valid_dep, arc_type_dict, add)
        corpus.append((dev_corpus, dependencies))
    else:
        corpus.append((dev_corpus, None))
    # get word dict
    words = [w for sub_corpus, _ in corpus for sent in sub_corpus[0] for w in sent ]
    # Special treatment for the final PubMed experiments
    #words = [w for sent in train_corpus[0] for w in sent ]
    words2idx = {OOV: 0}
    for w in words:
        if w not in words2idx:
            words2idx[w] = len(words2idx)    
    print ('voc_size:', len(words2idx))
    if dep:
        print ('arc_type_dict:', len(arc_type_dict), arc_type_dict)
    train_set_x, train_set_y, train_set_idx = [], [], [] 
    valid_set_x, valid_set_y, valid_set_idx = [], [], []
    test_set_x, test_set_y, test_set_idx = [], [], []
    
    if dep:
        train_set_dep = []
        valid_set_dep = []
        test_set_dep = []
        print ('load dependencies as well!!!')
    else:
        train_set_dep, valid_set_dep, test_set_dep = None, None, None
        #train_set_dep, valid_set_dep = None, None
    train_corpus, dev_corpus = corpus
    corp, dependencies = train_corpus
    x, y, idx = corp
    print ('check entity of training data')
    check_entity(x, idx)
    collect_data(train_set_x, train_set_y, train_set_idx, train_set_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add)
    corp, dependencies = dev_corpus
    x, y, idx = corp
    print ('check entity of dev data')
    check_entity(x, idx)
    collect_data(valid_set_x, valid_set_y, valid_set_idx, valid_set_dep, x, y, idx, dependencies, words2idx, arc_type_dict, dep, add)
    train = [train_set_x, train_set_y, train_set_idx]
    valid = [valid_set_x, valid_set_y, valid_set_idx]
    if test_path is not None:
        test = [test_set_x, test_set_y, test_set_idx]
    if dep:
        train.append(train_set_dep)
        valid.append(valid_set_dep)
        if test_path is not None:
            test.append(test_set_dep)
    else:
        train.append(None)
        valid.append(None)
        if test_path is not None:
            test.append(None)
    labels2idx = {'+':1, '-':0}
    dics = {'words2idx': words2idx, 'labels2idx': labels2idx}
    if dep:
        dics['arcs2idx'] = arc_type_dict
    if test_path is not None:
        return [train, valid, test, dics]
    return [train, valid, valid, dics]


if __name__ == '__main__':
    #eval(sys.argv[1])(sys.argv[2], sys.argv[3])
    #quick_sample(sys.argv[1], sys.argv[2])
    #quick_check(sys.argv[1], sys.argv[2])
    #gen_MST_from_json(sys.argv[1], sys.argv[2], sys.argv[3])
    eval(sys.argv[1])(*sys.argv[2:])
    #quick_split(sys.argv[1], 5)
    exit(0)
    train, valid, test, dics = load_data(train_path=sys.argv[1], valid_path=sys.argv[2], test_path=sys.argv[3])
    idx2word = dict((k, v) for v, k in dics['words2idx'].iteritems())
    for k,v in idx2word.iteritems():
	print (k,v)
