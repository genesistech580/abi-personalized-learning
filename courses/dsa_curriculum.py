"""Original starter content; lecturers review questions and equivalence before use."""
TOPICS = [
    "Introduction to Data Structures", "Arrays", "Linked Lists", "Stacks and Queues", "Searching and Sorting",
]
NOTES = [
    "A data structure organizes data and supports operations such as accessing, inserting, deleting and searching. An algorithm is a finite sequence of steps for solving a problem. Choose a representation by the operations needed, the amount of data, and time and memory costs. Correctness means producing the required result for all valid inputs, including empty and boundary cases. Constant time O(1) does not grow with the number of stored items under the stated model; a full scan is O(n). Big-O describes an upper bound on growth, not an exact number of seconds.",
    "An array stores elements in indexed positions. A zero-based array with n elements has valid indices 0 through n-1. A conventional contiguous array supports indexed access in O(1) time. Searching an unsorted array takes O(n) time in the worst case. Inserting into the middle may require shifting elements and therefore O(n) work. A dynamic array can allocate a larger block when it fills; appending is typically amortized O(1), although a resize can take O(n). Always check bounds before reading or writing an index.",
    "A singly linked list consists of nodes containing data and a reference to the next node. The head identifies the first node; the last node has no successor. Nodes need not occupy adjacent memory locations. To reach an arbitrary position, traversal follows links from the head and takes O(n) time in the worst case. Inserting at the head is O(1). Deleting after a known predecessor can be O(1), but locating that predecessor may take O(n). A doubly linked node has both next and previous references. Keeping a tail reference supports O(1) append with a suitable implementation.",
    "A stack removes items in last-in, first-out order (LIFO). Push adds an item at the top, pop removes the top item, and peek reads the top without removing it. A queue removes items in first-in, first-out order (FIFO). Enqueue adds at the rear and dequeue removes at the front. Removing from an empty stack or queue is underflow unless the interface provides another empty-case result. Function calls and undo operations are typical stack applications. Waiting jobs processed in arrival order are a typical queue application.",
    "Linear search checks items sequentially and works on unsorted input; its worst-case cost is O(n). Binary search requires an ordered searchable range and repeatedly discards half of that range, taking O(log n) comparisons in the worst case. Sorting arranges items according to an order. Insertion sort is useful for small or nearly sorted inputs; its best case is O(n) and its worst case is O(n squared). Merge sort divides input, sorts parts, and merges them in O(n log n) time. A stable sort preserves the relative order of equal-key records. State whether a complexity claim is a best, average or worst case.",
]
EXAMPLES = [
    "Example: a contact directory needs fast lookup, while a print queue needs arrival-order processing. List the operations first; then compare candidate structures. To test a maximum-finding algorithm, include a single value, repeated values and negative values, and explicitly handle an empty input.",
    "Example: for A = [4, 7, 9, 12], A[0] is 4 and A[2] is 9. Inserting 6 at index 1 gives [4, 6, 7, 9, 12] after shifting later items. The last valid index is now 4. Trace every changed position rather than assuming insertion is constant time.",
    "Example: head -> 10 -> 20 -> None. To insert 5 at the front, create a node with value 5, set its next reference to the old head, and then set head to the new node. The result is 5 -> 10 -> 20 -> None. The old chain must remain reachable.",
    "Example: pushing A, B and C onto a stack makes C the next pop. Enqueuing A, B and C into a queue makes A the next dequeue. Trace an interleaving of additions and removals and record which item remains at the top or front after each operation.",
    "Example: search for 7 in [1, 3, 5, 7, 9]. With zero-based inclusive bounds, the initial middle is index 2 (value 5). Search the right part; the next middle is index 3 (value 7). For sorting [3, 1, 2], insertion sort inserts 1 before 3, then inserts 2 between 1 and 3.",
]
EXERCISES = [
    "Describe an interface for a student record collection. List access, insertion, deletion and search operations. Compare two possible representations. Write pseudocode to find the largest value and define behavior for empty input.",
    "Trace indexed reads and a middle insertion. Write a bounds-checked function to find the largest array element. Test a one-element array, duplicates and negative values. Explain the difference between worst-case resizing cost and amortized append cost.",
    "Draw a three-node singly linked list. Implement insert-at-head and traversal. Test an empty list and a one-node list. Explain which operations need a predecessor or tail reference and how searching for a node changes the full operation cost.",
    "Trace push, pop, enqueue and dequeue with at least six operations. Implement a stack and a queue with explicit empty checks. Test repeated empty removals. Explain why removing from the front of a dynamic array may be inefficient for a queue.",
    "Trace linear and binary search on the same sorted input. Implement binary search with a documented interval convention. Trace insertion sort. Test duplicates, empty input and absent keys. Compare the cost of sorting once and performing many searches with repeated linear searches.",
]


def question_pairs(topic):
    # Each tuple gives two parallel prompts, one correct option and two distractors.
    if topic == 0:
        return [
            ("What is the main purpose of a data structure?", "Why do programs use data structures?", "To organize data and support operations", "To remove every algorithm", "To guarantee zero memory use"),
            ("Which description defines an algorithm?", "What best describes an algorithm for a task?", "A finite sequence of problem-solving steps", "A collection with no operations", "A random set of results"),
            ("Which matters when choosing a data structure?", "What should guide the choice of a representation?", "The required operations and their costs", "Only the name of the programming language", "Only the color of the interface"),
            ("What does O(1) indexed access mean?", "How does a constant-time operation scale with input size?", "Its work is bounded independently of input size", "It always takes one second", "It must inspect every item"),
            ("What is the cost of visiting n items once?", "What growth describes a single full scan of n elements?", "O(n)", "O(1)", "O(n squared)"),
            ("What is a time-space trade-off?", "Why might a faster implementation need more storage?", "Extra memory can reduce some operation costs", "Time and storage are always identical", "Using memory always makes operations slower"),
            ("What establishes algorithm correctness?", "What must a correct solution satisfy?", "The required result for every valid input", "A fast result on one example only", "The shortest source code"),
            ("Which structure models jobs processed in arrival order?", "Which structure fits a first-arriving customer served first?", "A queue", "A stack", "An unordered set with arbitrary removal"),
            ("What does worst-case complexity describe?", "What is the meaning of a worst-case running-time bound?", "The largest cost among inputs of a given size", "The fastest example ever seen", "Only the average of two tests"),
            ("Which boundary case should a collection algorithm consider?", "What special input should collection processing test?", "An empty collection", "Only a large positive-valued collection", "Only one already-successful example"),
        ]
    if topic == 1:
        return [
            ("For A=[3,6,9,12], what is A[2]?", "For A=[4,8,12,16], what is A[2]?", ("9", "12"), ("6", "8"), ("12", "16")),
            ("What is the last valid zero-based index for 8 elements?", "What is the last valid zero-based index for 6 elements?", ("7", "5"), ("8", "6"), ("9", "7")),
            ("How is a conventional array stored?", "What layout supports direct indexed array access?", "In contiguous element positions", "Only as separately linked nodes", "Without any storage"),
            ("What is indexed access cost in a conventional array?", "What is the time to read a known array index?", "O(1)", "O(n)", "O(n squared)"),
            ("What is worst-case search cost in an unsorted array?", "How much work may finding an absent value in an unsorted array require?", "O(n)", "O(1)", "O(log n) without ordering"),
            ("Why can insertion into an array's middle take O(n)?", "What can make an array insertion expensive?", "Later elements may need shifting", "Indexed access is impossible", "Every element loses its value"),
            ("What should happen before accessing A[n] in a length-n array?", "How should a program handle an index outside 0 through n-1?", "Check bounds and reject or handle the invalid index", "Always read it as the last element", "Assume it is index zero"),
            ("What is typical amortized dynamic-array append cost?", "With geometric growth, what is amortized append time?", "O(1)", "O(n squared)", "O(log n) for every append"),
            ("What is the sum of [2,4,6]?", "What is the sum of [3,6,9]?", ("12", "18"), ("6", "9"), ("10", "15")),
            ("Why can a dynamic-array resize take O(n)?", "What work can occur when a dynamic array grows its backing storage?", "Existing elements may be copied to a larger block", "Every append must sort the data", "The array becomes a linked list automatically"),
        ]
    if topic == 2:
        return [
            ("What does a singly linked node normally contain?", "Which fields are essential in a simple singly linked node?", "Data and a next reference", "Only an array index", "Only a previous reference"),
            ("What identifies the first linked-list node?", "Which reference starts traversal of a singly linked list?", "The head", "The middle index", "The capacity value"),
            ("What does the final next reference usually contain?", "How does a non-circular singly linked list mark its end?", "A null / None reference", "The second node's value", "An automatic duplicate node"),
            ("What is worst-case linked-list traversal time?", "How much work can reaching the last singly linked node take?", "O(n)", "O(1)", "O(log n) without extra indexing"),
            ("What is insert-at-head time with a known head reference?", "What is the cost of linking a new first node?", "O(1)", "O(n squared)", "O(n log n)"),
            ("When can deletion after a known predecessor be O(1)?", "With the predecessor already available, what does removing its next node require?", "Relinking a fixed number of references", "Sorting the whole list", "Shifting every later value"),
            ("What is worst-case access time for the kth singly linked position?", "Without an extra index, how is an arbitrary linked-list position reached?", "Traversal that can take O(n)", "Guaranteed O(1) by arithmetic", "Guaranteed O(log n) by binary search"),
            ("What distinguishes a doubly linked node?", "What extra link does a doubly linked list maintain?", "Both previous and next references", "Only the number of arrays", "A sorting algorithm in every node"),
            ("What can make linked-list append O(1)?", "Which maintained reference avoids scanning for the last node on append?", "A tail reference with suitable linking", "Only the list's display title", "A larger font size"),
            ("Must linked nodes be adjacent in memory?", "What memory layout is required for separate linked nodes?", "They need not be contiguous", "They must occupy one contiguous array", "They cannot store references"),
        ]
    if topic == 3:
        return [
            ("Which removal order does a stack use?", "What does stack LIFO mean?", "Last in, first out", "First in, first out", "Always remove the smallest value"),
            ("Which removal order does a queue use?", "What does queue FIFO mean?", "First in, first out", "Last in, first out", "Always remove the largest value"),
            ("After pushing A then B, which item is popped first?", "After pushing C then D, which item is popped first?", ("B", "D"), ("A", "C"), ("Both together", "Both together")),
            ("Enqueue A then B, then dequeue once. Which remains?", "Enqueue C then D, then dequeue once. Which remains?", ("B", "D"), ("A", "C"), ("No item", "No item")),
            ("What does push do?", "Which action adds a stack item?", "Add at the top", "Remove from the front", "Sort all items"),
            ("Where is an item added by enqueue?", "Which end normally receives a new queue item?", "The rear", "An arbitrary sorted position", "Both ends at once"),
            ("What does peek normally do?", "How is the next item inspected without removal?", "Read the top or front without changing the structure", "Delete every item", "Always add another item"),
            ("What is removing from an empty stack called?", "What condition must an empty dequeue handle?", "Underflow", "Successful sorting", "Array doubling"),
            ("Which structure models nested function calls?", "Which structure naturally supports undoing the latest action?", "A stack", "A FIFO queue", "An unordered bag with arbitrary removal"),
            ("Which structure fits a first-arrived print job served first?", "What structure fits a first-come-first-served waiting line?", "A queue", "A stack", "A list that always removes the largest value"),
        ]
    return [
        ("What input condition does binary search require?", "What must be true before ordinary binary search is applied?", "The searched range is sorted by the search key", "The range is always random", "Every value is identical"),
        ("What is binary search's worst-case comparison growth?", "How does repeatedly halving a sorted range scale?", "O(log n)", "O(n squared)", "O(n) for every search"),
        ("What index holds 7 in [2,5,7,9] with zero-based indexing?", "What index holds 8 in [3,6,8,10] with zero-based indexing?", "2", "1", "3"),
        ("Which is [4,1,3] in ascending order?", "Which is [6,2,5] in ascending order?", ("[1,3,4]", "[2,5,6]"), ("[4,3,1]", "[6,5,2]"), ("[3,1,4]", "[5,2,6]")),
        ("What is merge sort's usual worst-case time?", "What worst-case bound describes standard merge sort?", "O(n log n)", "O(1)", "O(log n)"),
        ("What is standard insertion sort's best-case time on sorted input?", "How does insertion sort behave in its best already-sorted case?", "O(n)", "O(n squared) in every case", "O(1) regardless of length"),
        ("How many halvings reduce 16 to 1?", "How many halvings reduce 32 to 1?", ("4", "5"), ("8", "16"), ("16", "32")),
        ("Which pair does bubble sort compare in a normal pass?", "What kind of comparison drives a typical bubble-sort pass?", "Adjacent elements", "Only the first and last elements", "Only values from different arrays"),
        ("What does a stable sorting algorithm preserve?", "What stays unchanged for equal-key records in a stable sort?", "Their original relative order", "Every original array position", "The input's unsorted order for all keys"),
        ("Which search works without sorting first?", "Which method can scan an unsorted collection directly?", "Linear search", "Ordinary binary search", "Binary search on arbitrary positions"),
    ]
