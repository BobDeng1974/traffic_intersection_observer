#!/usr/local/bin/python
# coding: utf-8
# Automaton Class
# Steve Guo, Tung M. Phan
# California Institute of Technology
# July 12, 2018

import sys
sys.path.append('..')
from random import sample
import numpy as np
import math, itertools
from graphviz import Digraph
from prepare import queue

# General state class.
class State:
    def __init__(self, name, composite_list = None):
        if isinstance(name, str) or isinstance(name, int):
        #if not isinstance(name, (str,int)): # by Jiaqi
            TypeError('state name must be of type string or int!')
        if isinstance(name, int):
            name = str(name) # convert name to string
        self.name = name.upper() # convert name to uppercase
        if composite_list == None:
            self.composite_list = list()
            self.composite_list.append(self)
        else:
            self.composite_list = composite_list

def product(state1, state2):
    composite_list = state1.composite_list + state2.composite_list
    new_name = '('
    for state in composite_list:
        new_name += state.name + ', '
    new_name = new_name[:-2]
    new_name += ')'
    return State(new_name, composite_list)

def compact_product(state1, state2):
    composite_list = state1.composite_list + state2.composite_list
    new_name = ''
    for state in composite_list:
        new_name += state.name
    return State(new_name, composite_list)

# General transition class. Transition is a string from the alphabet.
class Transition:
    def __init__(self, start = None, end = None, label = None):
        self.startState = start
        self.endState = end
        self.label = label

    def set_start_state(self, start):
        self.startState = start

    def set_end_state(self, end):
        self.endState = end

    def set_label(self, label):
        self.label = label

    def get_start(self):
        return '(' + self.startState.name + ')'

    def get_end(self):
        return '(' + self.endState.name + ')'

    def get_label(self):
        return self.label

    def print_transition(self):
        print(self.get_start() + ' ----> ' + self.get_end())

    def show(self):
        return self.label

# General transition class for guard (where the guard is a set of inequalities.)
class guardTransition(Transition):
    def __init__(self, start = None, end = None, guard = True, action = None, actionType = None):
        Transition.__init__(self, start, end)
        self.guard = guard # guard should be a dictionary of inequalities
        # actually, now guard is a string representing a boolean

        # actionType is ?, !, or #, corresponding to input, output, and internal respectively
        if actionType not in {'?', '!', '#', ''}:
            TypeError('actionType must be either ?, !, or #!')
        self.actionType = actionType

        if self.actionType == '':
            self.action = ''
        elif isinstance(action, str):
            TypeError('action must be of type str!')
        self.action = action

    def show(self):
        transtext = ''
        # guard can be string
        if isinstance(self.guard, str):
            transtext = '[' + self.guard
        elif self.guard == False:
            return transtext
        elif self.guard == True:
            transtext += 'True'
        transtext += ' | ' + self.actionType + self.action + ']'
        return transtext

    def print_transition(self):
        print(self.get_start() + ' --[' + self.show() + ']--> ' + self.get_end())

# General finite automaton. 
class Automaton():
    def __init__(self):
        self.alphabet = set()
        self.transitions_dict = {} # transitions_dict[state] is the set of transitions from that state
        self.startStates = set()
        self.endStates = set()
        self.states = set()

    def add_state(self, state, end_state = False, start_state = False):
        if end_state:
            self.endStates.add(state)
        if start_state:
            self.startStates.add(state)

        self.states.add(state)
        self.transitions_dict[state] = set()

    def add_transition(self, transition):
        self.transitions_dict[transition.startState].add(transition)

    def remove_state(self, state):
        # deletes all transitions leading to that state
        for key in self.transitions_dict:
            transitions = self.transitions_dict[key]
            for trans in transitions:
                if trans.endState == state:
                    self.transitions_dict[key].remove(trans)

        # deletes the state
        self.transitions_dict.pop(state)
        self.states.remove(state)
        try:
            self.startStates.remove(state)
            self.endStates.remove(state)
        except KeyError:
            pass

    def convert_to_digraph(self):
        automata = Digraph(format='png')
        for state in self.states.union({self.fail_state}):
            # adds nodes
            automata.attr('node', color = 'gray', shape = 'circle', style='filled', fixedsize='false')
            if state in self.startStates:
                automata.attr('node', color = 'gray', style='filled',  fixedsize = 'false', shape='circle')
            automata.node(state.name, state.name)
        # adds transitions
        for state in self.states:
            transit = self.transitions_dict[state] # this is a set of transitions from the state
            for trans in transit:
                if trans != False:
                    state2 = trans.endState
                    transtext = trans.show()
                    automata.edge(state.name, state2.name, label = transtext)
        return automata

    # BFS algorithm to find reachable nodes
def find_reachable_set(automaton):
    reachable_set = set()
    search_queue = queue.Queue()
    # initialize queue
    for start in automaton.startStates:
        search_queue.enqueue(start)
        reachable_set.add(start)
    while search_queue.len() > 0:
        top = search_queue.pop()
        for trans in automaton.transitions_dict[top]:
            if not(trans == False):
                if not (trans.endState in reachable_set):
                    reachable_set.add(trans.endState)
                    search_queue.enqueue(trans.endState)
    return reachable_set

class InterfaceAutomaton(Automaton):
    def __init__(self, inputAlphabet = set(), outputAlphabet = set(), internalAlphabet = set(), fail_state = State('⊥'), prestart_state = State('')):
        Automaton.__init__(self)
        self.fail_state = fail_state
        self.prestart_state = prestart_state
        self.add_state(self.fail_state)
        self.input_alphabet = inputAlphabet
        self.output_alphabet = outputAlphabet
        self.internal_alphabet = internalAlphabet
        self.alphabet = self.input_alphabet.union(self.output_alphabet).union(self.internal_alphabet)

    def add_transition(self, transition):
        if transition != False:
            self.transitions_dict[transition.startState].add(transition)
            self.alphabet.add(transition.action)
            if transition.actionType == '?':
                self.input_alphabet.add(transition.action)
            elif transition.actionType == '!':
                self.output_alphabet.add(transition.action)
            elif transition.actionType =='#':
                self.internal_alphabet.add(transition.action)


    # also removes all states without transitions
    def trim(self):
        reachable_set = find_reachable_set(self)
        unreachable_set = self.states - reachable_set
        for key in self.transitions_dict:
            # removes transitions
            to_remove = set()
            for trans in self.transitions_dict[key]:
                if trans == False:
                    to_remove.add(trans)
            self.transitions_dict[key] = self.transitions_dict[key] - to_remove

        # removes states that are not reachable
        for node in unreachable_set:
            self.remove_state(node)

    # takes two guard transitions and returns their composition
def compose_guard_trans(tr1, tr2, node_dict):
    if (tr1.action != tr2.action and '' not in [tr1.actionType, tr2.actionType]) or tr1.guard == False or tr2.guard == False:
        return False
    if tr1.guard == True or tr1.guard == 'True':
        guard = tr2.guard
    elif tr2.guard == True or tr2.guard == 'True':
        guard = tr1.guard
    elif isinstance(tr1.guard, str) and isinstance(tr2.guard, str):
        guard = tr1.guard + ' ∧ ' + tr2.guard

    newStart = node_dict[(tr1.startState, tr2.startState)]
    newEnd = node_dict[(tr1.endState, tr2.endState)]

    # assumption is that either both are inequalities or strings
    if tr1.actionType == '':
        newType = tr2.actionType
        action = tr2.action
    else:
        action = tr1.action
        newType = tr1.actionType
        if {tr1.actionType, tr2.actionType} == {'!', '?'} or tr2.actionType == '#':
            newType = '#'
    return guardTransition(newStart, newEnd, guard, action, newType)

def conjunct_may_trans(tr1, tr2, node_dict):
    if tr1.action != tr2.action or tr1.actionType != tr2.actionType:
        return False
    if tr1.guard == True or tr1.guard == 'True':
        guard = tr2.guard
    elif tr2.guard == True or tr2.guard == 'True':
        guard = tr1.guard
    else:
        guard = tr1.guard + ' ∧ ' + tr2.guard

    newStart = node_dict[(tr1.startState, tr2.startState)]
    newEnd = node_dict[(tr1.endState, tr2.endState)]

    return guardTransition(newStart, newEnd, guard, tr1.action, tr1.actionType)

def conjunct_must_trans(tr1, tr2, node_dict):
    if tr1.action != tr2.action or tr1.actionType != tr2.actionType:
        return False
    if tr1.guard == True or tr1.guard == 'True':
        guard = 'True'
    elif tr2.guard == True or tr2.guard == 'True':
        guard = 'True'
    else:
        guard = tr1.guard + ' ∨ ' + tr2.guard

    newStart = node_dict[(tr1.startState, tr2.startState)]
    newEnd = node_dict[(tr1.endState, tr2.endState)]

    return guardTransition(newStart, newEnd, guard, tr1.action, tr1.actionType)


def compose_interfaces(interface_1, interface_2):
    new_interface = InterfaceAutomaton()
    dict1 = interface_1.transitions_dict
    dict2 = interface_2.transitions_dict
    node_dict = dict() # maintain references to states being composed
    for key1 in dict1:
        for key2 in dict2:
            newstate = product(key1, key2)
            if key1 == interface_1.fail_state or key2 == interface_2.fail_state:
                node_dict[(key1, key2)] = new_interface.fail_state
            else:
                node_dict[(key1, key2)] = product(key1,key2)

    for key1 in dict1:
        for key2 in dict2:
            newstate = node_dict[(key1, key2)]
            new_interface.add_state(newstate, start_state = key1 in interface_1.startStates and key2 in interface_2.startStates)
            for trans1 in dict1[key1]:
                for trans2 in dict2[key2]:
                    new_interface.transitions_dict[newstate].add(compose_guard_trans(trans1, trans2, node_dict))
    # new_interface.trim()
    return new_interface

def construct_automaton(state_set, translist, starts):
    new_interface = InterfaceAutomaton()
    string_state_dict = dict()
    string_state_dict['⊥'] = new_interface.fail_state # add failure state manually
    # state_set is a list of strings representing state names
    for state in state_set:
        newstate = State(state)
        new_interface.add_state(newstate)
        string_state_dict[state] = newstate
    for start in starts:
        new_interface.startStates.add(string_state_dict[start])
    # translist is a dictionary; the key is a tuple of strings representing the states of the transition, and the value is a list:
    # (guardtext, action, action_type)
    for key in translist:
        state1 = string_state_dict[key[0]]
        state2 = string_state_dict[key[1]]
        guard = translist[key][0]
        action = translist[key][1]
        action_type = translist[key][2]
        new_interface.add_transition(guardTransition(start = state1, end = state2,  guard = guard, action = action, actionType = action_type))
    new_interface.trim()
    return new_interface
