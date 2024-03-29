Seeker
======
An esoteric programming language that uses pathfinding to determine where the instruction pointer should move next.

Overview
--------
Seeker programs consist of a bidirectional graph. Each node holds a single value and can be connected to any number of other nodes. Values are interpreted as opcodes or opcode arguments.

When a Seeker thread has processed the value of its current node, its instruction pointer moves forward - but what is forward in a graph? Seeker uses pathfinding to determine that. Each thread not only keeps track of what node it is currently at, but also what node it is heading for. A thread will always move along the shortest path to its destination.

Quick instructions
------------------
To run a .skr file (requires Python 3.x):
```
python seeker.py filename.skr
```
To see all available options:
```
python seeker.py -h
```

Opcodes
-------
The following opcodes are available. Most opcodes take one or more arguments. When an opcode requires arguments, a thread collects the values of subsequent nodes until is the number of arguments is met. The opcode is then executed.
```
1: set new destination (node id)
2: change connection (node id, node id, 0 or less = disconnect if connected / more than 0 = connect if not connected)
3: change node (node id, 0 or less = destroy if exists / more than 0 = create if not exists)
4: increment node value (node id)
5: decrement node value (node id)
6: copy value from node to node (from node id, to node id)
```
When Seeker is started in extended mode, the following opcodes become available:
```
7: create new thread (start node id, destination node id)
8: breakpoint ()
```

.skr syntax
-----------
Seeker programs can be loaded from .skr files. The syntax is quite simple.

To create a node:
```
node_id : value
```
To connect two nodes:
```
node_id - node_id
```
Node ids and values must be integer numbers. Statements must be separated by non-digit characters (excluding the - and : characters). Nodes can be connected before they have been created - Seeker is smart enough to connect the nodes afterwards.

Examples
--------
The following example prints "hello world":
```
Instruction nodes
0:1     0-1     Set course for node seven
1:7     1-2
2:2     2-3     Disconnect start and end nodes (so the program can terminate instead of backtrack)
3:0     3-4
4:27    4-5
5:0     5-6
6:1     6-7     Set course for end node
7:27    7-8
8:6     8-9     Copy character to following connect/disconnect (to terminate program after printing last character)
9:100   9-10
10:14   10-11
11:2    11-12   Disconnect next point after the last character has been printed, to terminate the program
12:14   12-13
13:15   13-14
14:0    14-15       (character is copied here, if it's zero it disconnects)
15:6    15-16   Print character (copy to IO node)
16:100  16-17
17:0    17-18
18:4    18-19   Increment copy pointer
19:9    19-20
20:4    20-21   Increment print pointer
21:16   21-22
22:2    22-23   Connect start and end nodes again to loop back to the start
23:0    23-24
24:27   24-25
25:1    25-26
26:1    26-27   Set course for the start (just a bit beyond it so the start can set the destination again too)
27:1

Data nodes
100: 104    hello world
101: 101
102: 108
103: 108
104: 111
105: 32
106: 119
107: 111
108: 114
109: 108
110: 100
111: 0      Zero terminated string (zero value is used to disconnect nodes, see above)
```
Which, to Seeker, is the same as:
```
0:1 0-1 1:7 1-2 2:2 2-3 3:0 3-4 4:27 4-5 5:0 5-6 6:1 6-7 7:27 7-8 8:6 8-9 9:100 9-10 10:14 10-11 11:2 11-12 12:14 12-13 13:15 13-14 14:0 14-15 15:6 15-16 16:100 16-17 17:0 17-18 18:4 18-19 19:9 19-20 20:4 20-21 21:16 21-22 22:2 22-23 23:0 23-24 24:27 24-25 25:1 25-26 26:1 26-27 27:1 100:104 101:101 102:108 103:108 104:111 105:32 106:119 107:111 108:114 109:108 110:100 111:0
```
TODO: Insert visualization of graph structure as image.

Details
-------
A Seeker programs main thread starts at node number 0 and is heading for node number 1. Without these two nodes, a Seeker program can't start.

Note that node 0 is also the special IO node: copying from this node reads an input byte, or -1 if there is no input. Copying to this node writes the value, converted to a byte, to the output.

If a destination node can be reached through multiple routes of equal length, no guarantees are given as to which route is chosen.

If a thread arrives at it's destination node, it is terminated. Be sure to give threads new destinations to keep them running.

If a thread can't find a route to it's destination node, it stalls. It will only resume when it can find a route again. If all threads in a program are stalled, the program terminates, because then there are no threads left that can unblock other threads by restoring connections between nodes.

Be aware that setting a threads destination might cause it to move 'backwards'. This may cause a thread to process values that were previously used as opcode arguments as opcodes instead (possibly treating the previous opcode as an argument).