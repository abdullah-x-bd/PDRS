use std::collections::HashMap;
use std::env;
use std::fs;
use std::time::Instant;

#[derive(Clone, Debug)]
enum RawNode {
    Terminal {
        name: String,
    },
    Choice {
        name: String,
        branches: Vec<(String, String)>,
    },
    Range {
        name: String,
        start: i64,
        stop: i64,
        target: String,
    },
}

#[derive(Clone, Debug)]
enum Node {
    Terminal,
    Choice {
        branches: Vec<(String, usize)>,
    },
    Range {
        start: i64,
        stop: i64,
        target: usize,
    },
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum Token {
    Str(String),
    Int(i64),
}

#[derive(Debug)]
struct Schema {
    name: String,
    root: usize,
    nodes: Vec<Node>,
    counts: Vec<u64>,
    max_depth: usize,
}

fn parse_u64(text: &str, label: &str) -> Result<u64, String> {
    text.parse::<u64>()
        .map_err(|_| format!("invalid {label}: {text}"))
}

fn parse_i64(text: &str, label: &str) -> Result<i64, String> {
    text.parse::<i64>()
        .map_err(|_| format!("invalid {label}: {text}"))
}

fn checked_add(left: u64, right: u64) -> Result<u64, String> {
    left.checked_add(right)
        .ok_or_else(|| "domain cardinality exceeds u64".to_string())
}

fn checked_mul(left: u64, right: u64) -> Result<u64, String> {
    left.checked_mul(right)
        .ok_or_else(|| "domain cardinality exceeds u64".to_string())
}

fn load_schema(path: &str) -> Result<Schema, String> {
    let content = fs::read_to_string(path).map_err(|e| format!("cannot read {path}: {e}"))?;
    let mut lines = content
        .lines()
        .filter(|line| !line.is_empty() && !line.starts_with('#'));
    if lines.next() != Some("PDRS_IR_V1") {
        return Err("invalid IR magic".to_string());
    }
    let mut schema_name: Option<String> = None;
    let mut version: Option<String> = None;
    let mut root_name: Option<String> = None;
    let mut raw_nodes: Vec<RawNode> = Vec::new();
    for line in lines {
        let parts: Vec<&str> = line.split('\t').collect();
        if parts.len() < 2 {
            return Err(format!("malformed IR line: {line}"));
        }
        match parts[0] {
            "name" => schema_name = Some(parts[1].to_string()),
            "version" => version = Some(parts[1].to_string()),
            "root" => root_name = Some(parts[1].to_string()),
            "node" => {
                if parts.len() < 3 {
                    return Err("malformed node line".to_string());
                }
                match parts[1] {
                    "T" => {
                        if parts.len() != 3 {
                            return Err("malformed terminal node".to_string());
                        }
                        raw_nodes.push(RawNode::Terminal {
                            name: parts[2].to_string(),
                        });
                    }
                    "C" => {
                        if parts.len() < 6 {
                            return Err("malformed choice node".to_string());
                        }
                        let branch_count = parse_u64(parts[4], "branch count")? as usize;
                        if parts.len() != 5 + 2 * branch_count {
                            return Err("choice branch count mismatch".to_string());
                        }
                        let mut branches = Vec::with_capacity(branch_count);
                        for index in 0..branch_count {
                            branches.push((
                                parts[5 + 2 * index].to_string(),
                                parts[6 + 2 * index].to_string(),
                            ));
                        }
                        raw_nodes.push(RawNode::Choice {
                            name: parts[2].to_string(),
                            branches,
                        });
                    }
                    "R" => {
                        if parts.len() != 7 {
                            return Err("malformed range node".to_string());
                        }
                        let start = parse_i64(parts[4], "range start")?;
                        let stop = parse_i64(parts[5], "range stop")?;
                        if stop < start {
                            return Err("range stop is below start".to_string());
                        }
                        raw_nodes.push(RawNode::Range {
                            name: parts[2].to_string(),
                            start,
                            stop,
                            target: parts[6].to_string(),
                        });
                    }
                    other => return Err(format!("unknown node type {other}")),
                }
            }
            other => return Err(format!("unknown IR record {other}")),
        }
    }
    let name = schema_name.ok_or_else(|| "missing schema name".to_string())?;
    let _version = version.ok_or_else(|| "missing schema version".to_string())?;
    let root_name = root_name.ok_or_else(|| "missing root".to_string())?;
    if raw_nodes.is_empty() {
        return Err("schema has no nodes".to_string());
    }
    let mut lookup = HashMap::new();
    for (index, raw) in raw_nodes.iter().enumerate() {
        let node_name = match raw {
            RawNode::Terminal { name }
            | RawNode::Choice { name, .. }
            | RawNode::Range { name, .. } => name,
        };
        if lookup.insert(node_name.clone(), index).is_some() {
            return Err(format!("duplicate node {node_name}"));
        }
    }
    let root = *lookup
        .get(&root_name)
        .ok_or_else(|| format!("missing root node {root_name}"))?;
    let mut nodes = Vec::with_capacity(raw_nodes.len());
    for raw in raw_nodes {
        nodes.push(match raw {
            RawNode::Terminal { .. } => Node::Terminal,
            RawNode::Choice { branches, .. } => {
                let resolved = branches
                    .into_iter()
                    .map(|(value, target)| {
                        lookup
                            .get(&target)
                            .copied()
                            .map(|index| (value, index))
                            .ok_or_else(|| format!("missing target node {target}"))
                    })
                    .collect::<Result<Vec<_>, _>>()?;
                Node::Choice { branches: resolved }
            }
            RawNode::Range {
                start,
                stop,
                target,
                ..
            } => {
                let target = *lookup
                    .get(&target)
                    .ok_or_else(|| format!("missing target node {target}"))?;
                Node::Range {
                    start,
                    stop,
                    target,
                }
            }
        });
    }
    let mut counts = vec![0u64; nodes.len()];
    let mut states = vec![0u8; nodes.len()];
    let mut max_depth = 0usize;
    compute_count(root, 0, &nodes, &mut counts, &mut states, &mut max_depth)?;
    if states.iter().any(|state| *state != 2) {
        return Err("unreachable node detected".to_string());
    }
    Ok(Schema {
        name,
        root,
        nodes,
        counts,
        max_depth,
    })
}

fn compute_count(
    index: usize,
    depth: usize,
    nodes: &[Node],
    counts: &mut [u64],
    states: &mut [u8],
    max_depth: &mut usize,
) -> Result<u64, String> {
    if depth > 100_000 {
        return Err("schema depth limit exceeded".to_string());
    }
    match states[index] {
        1 => return Err("cycle detected".to_string()),
        2 => return Ok(counts[index]),
        _ => {}
    }
    states[index] = 1;
    *max_depth = (*max_depth).max(depth);
    let total = match &nodes[index] {
        Node::Terminal => 1,
        Node::Choice { branches } => {
            let mut total = 0u64;
            for (_, target) in branches {
                total = checked_add(
                    total,
                    compute_count(*target, depth + 1, nodes, counts, states, max_depth)?,
                )?;
            }
            total
        }
        Node::Range {
            start,
            stop,
            target,
        } => {
            let width = (*stop - *start + 1) as u64;
            checked_mul(
                width,
                compute_count(*target, depth + 1, nodes, counts, states, max_depth)?,
            )?
        }
    };
    if total == 0 {
        return Err("empty domain".to_string());
    }
    counts[index] = total;
    states[index] = 2;
    Ok(total)
}

impl Schema {
    fn count(&self) -> u64 {
        self.counts[self.root]
    }

    fn rank(&self, tokens: &[Token]) -> Result<u64, String> {
        let mut node_index = self.root;
        let mut position = 0usize;
        let mut rank = 0u64;
        loop {
            match &self.nodes[node_index] {
                Node::Terminal => {
                    if position != tokens.len() {
                        return Err("trailing tokens".to_string());
                    }
                    return Ok(rank);
                }
                Node::Choice { branches } => {
                    let token = tokens
                        .get(position)
                        .ok_or_else(|| "missing choice token".to_string())?;
                    position += 1;
                    let selected = match token {
                        Token::Str(value) => value,
                        _ => return Err("choice requires string".to_string()),
                    };
                    let mut offset = 0u64;
                    let mut target = None;
                    for (value, branch_target) in branches {
                        if value == selected {
                            target = Some(*branch_target);
                            break;
                        }
                        offset = checked_add(offset, self.counts[*branch_target])?;
                    }
                    node_index = target.ok_or_else(|| "unknown choice".to_string())?;
                    rank = checked_add(rank, offset)?;
                }
                Node::Range {
                    start,
                    stop,
                    target,
                } => {
                    let token = tokens
                        .get(position)
                        .ok_or_else(|| "missing range token".to_string())?;
                    position += 1;
                    let value = match token {
                        Token::Int(value) => *value,
                        _ => return Err("range requires integer".to_string()),
                    };
                    if value < *start || value > *stop {
                        return Err("integer outside range".to_string());
                    }
                    rank = checked_add(
                        rank,
                        checked_mul((value - *start) as u64, self.counts[*target])?,
                    )?;
                    node_index = *target;
                }
            }
        }
    }

    fn unrank(&self, index: u64) -> Result<Vec<Token>, String> {
        if index >= self.count() {
            return Err("rank outside domain".to_string());
        }
        let mut node_index = self.root;
        let mut remainder = index;
        let mut output = Vec::with_capacity(self.max_depth);
        loop {
            match &self.nodes[node_index] {
                Node::Terminal => {
                    if remainder != 0 {
                        return Err("internal remainder invariant".to_string());
                    }
                    return Ok(output);
                }
                Node::Choice { branches } => {
                    let mut offset = 0u64;
                    let mut selected = None;
                    for (value, target) in branches {
                        let next = checked_add(offset, self.counts[*target])?;
                        if remainder < next {
                            remainder -= offset;
                            selected = Some((value.clone(), *target));
                            break;
                        }
                        offset = next;
                    }
                    let (value, target) =
                        selected.ok_or_else(|| "choice unrank invariant".to_string())?;
                    output.push(Token::Str(value));
                    node_index = target;
                }
                Node::Range {
                    start,
                    stop,
                    target,
                } => {
                    let block = self.counts[*target];
                    let local = remainder / block;
                    remainder %= block;
                    let value = *start + local as i64;
                    if value > *stop {
                        return Err("range unrank invariant".to_string());
                    }
                    output.push(Token::Int(value));
                    node_index = *target;
                }
            }
        }
    }
}

fn canonical_tokens(tokens: &[Token]) -> String {
    tokens
        .iter()
        .map(|token| match token {
            Token::Str(value) => format!("S:{value}"),
            Token::Int(value) => format!("I:{value}"),
        })
        .collect::<Vec<_>>()
        .join("|")
}

fn verify(path: &str) -> Result<(), String> {
    let schema = load_schema(path)?;
    let mut failures = 0u64;
    for index in 0..schema.count() {
        let tokens = schema.unrank(index)?;
        if schema.rank(&tokens)? != index {
            failures += 1;
        }
    }
    println!(
        "{{\"language\":\"rust\",\"schema\":\"{}\",\"count\":{},\"checked\":{},\"failures\":{}}}",
        schema.name,
        schema.count(),
        schema.count(),
        failures
    );
    if failures == 0 {
        Ok(())
    } else {
        Err(format!("{failures} failures"))
    }
}

fn vectors(path: &str, ranks_path: &str) -> Result<(), String> {
    let schema = load_schema(path)?;
    let ranks = fs::read_to_string(ranks_path).map_err(|e| format!("cannot read ranks: {e}"))?;
    for line in ranks.lines().filter(|line| !line.is_empty()) {
        let rank = parse_u64(line, "rank")?;
        println!("{}\t{}", rank, canonical_tokens(&schema.unrank(rank)?));
    }
    Ok(())
}

fn bench(path: &str, iterations: u64) -> Result<(), String> {
    let schema = load_schema(path)?;
    let sample_count =
        usize::try_from(schema.count().min(4096)).map_err(|_| "sample count overflow")?;
    let mut samples = Vec::with_capacity(sample_count);
    let mut state = 0x9e3779b97f4a7c15u64;
    for _ in 0..sample_count {
        state = state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        samples.push(schema.unrank(state % schema.count())?);
    }
    let mut sink = 0u64;
    let started = Instant::now();
    for index in 0..iterations {
        sink ^= schema.rank(&samples[index as usize % sample_count])?;
    }
    let rank_ns = started.elapsed().as_nanos() as f64 / iterations as f64;
    let started = Instant::now();
    for index in 0..iterations {
        let rank = index.wrapping_mul(11400714819323198485) % schema.count();
        sink ^= schema.unrank(rank)?.len() as u64;
    }
    let unrank_ns = started.elapsed().as_nanos() as f64 / iterations as f64;
    println!("{{\"language\":\"rust\",\"schema\":\"{}\",\"count\":{},\"iterations\":{},\"rank_ns\":{:.6},\"unrank_ns\":{:.6},\"sink\":{}}}",
             schema.name, schema.count(), iterations, rank_ns, unrank_ns, sink);
    Ok(())
}

fn usage() {
    eprintln!("usage:\n  pdrs-native verify SCHEMA.pdrs\n  pdrs-native vectors SCHEMA.pdrs RANKS.txt\n  pdrs-native bench SCHEMA.pdrs ITERATIONS");
}

fn run() -> Result<(), String> {
    let args: Vec<String> = env::args().collect();
    match args.as_slice() {
        [_, command, path] if command == "verify" => verify(path),
        [_, command, path, ranks] if command == "vectors" => vectors(path, ranks),
        [_, command, path, iterations] if command == "bench" => {
            bench(path, parse_u64(iterations, "iterations")?)
        }
        _ => {
            usage();
            Err("invalid arguments".to_string())
        }
    }
}

fn main() {
    if let Err(error) = run() {
        eprintln!("pdrs-rust: {error}");
        std::process::exit(2);
    }
}
