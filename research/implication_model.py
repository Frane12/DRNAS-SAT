"""Construct a 2-CNF model using strongly connected implication components."""


def implication_model(n, clauses):
    graph = [[] for _ in range(2 * n)]
    reverse = [[] for _ in graph]
    for clause in clauses:
        indices = [2 * (abs(lit) - 1) + (lit < 0) for lit in clause]
        a, b = indices[0], indices[-1]
        for start, end in ((a ^ 1, b), (b ^ 1, a)):
            graph[start].append(end)
            reverse[end].append(start)
    seen = set()
    order = []
    for v in range(len(graph)):
        if v in seen:
            continue
        stack = [(v, iter(graph[v]))]
        seen.add(v)
        while stack:
            node, edges = stack[-1]
            child = next(edges, None)
            if child is None:
                order.append(node)
                stack.pop()
            elif child not in seen:
                seen.add(child)
                stack.append((child, iter(graph[child])))
    component = [-1] * len(graph)
    for i, v in enumerate(reversed(order)):
        if component[v] != -1:
            continue
        component[v] = i
        stack = [v]
        while stack:
            for child in reverse[stack.pop()]:
                if component[child] == -1:
                    component[child] = i
                    stack.append(child)
    if any(component[2 * i] == component[2 * i + 1] for i in range(n)):
        return None
    return [component[2 * i] > component[2 * i + 1] for i in range(n)]
