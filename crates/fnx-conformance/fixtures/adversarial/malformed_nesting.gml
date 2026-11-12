graph [
  directed 0
  node [
    id 0
    label "a"
    node [
      id 999
      label "nested_node_should_fail"
    ]
  ]
  edge [
    source 0
    target 0
    edge [
      source 1
      target 2
    ]
  ]
  node [
    id 1
    label "b"
  ]
  edge [
    source 0
    target 1
  ]
]
