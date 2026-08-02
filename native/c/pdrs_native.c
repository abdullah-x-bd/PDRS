#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define INITIAL_NODE_CAP 16
#define MAX_TOKENS_PER_LINE 8192

typedef enum { NODE_TERMINAL, NODE_CHOICE, NODE_RANGE } NodeType;

typedef struct {
    char *value;
    char *target_name;
    size_t target;
} Branch;

typedef struct {
    NodeType type;
    char *name;
    char *field;
    Branch *branches;
    size_t branch_count;
    int64_t start;
    int64_t stop;
    char *target_name;
    size_t target;
} Node;

typedef struct {
    char *name;
    char *version;
    char *root_name;
    size_t root;
    Node *nodes;
    size_t node_count;
    size_t node_cap;
    uint64_t *counts;
    unsigned char *states;
    size_t max_depth;
} Schema;

typedef struct {
    bool is_int;
    int64_t int_value;
    const char *str_value;
} Token;

typedef struct {
    Token *items;
    size_t len;
} TokenVec;

static void die(const char *message) {
    fprintf(stderr, "pdrs-c: %s\n", message);
    exit(2);
}

static void *xcalloc(size_t count, size_t size) {
    void *ptr = calloc(count, size);
    if (!ptr) die("out of memory");
    return ptr;
}

static void *xrealloc(void *ptr, size_t size) {
    void *next = realloc(ptr, size);
    if (!next) die("out of memory");
    return next;
}

static char *xstrdup(const char *value) {
    char *copy = strdup(value);
    if (!copy) die("out of memory");
    return copy;
}

static char *trim_newline(char *line) {
    size_t len = strlen(line);
    while (len > 0 && (line[len - 1] == '\n' || line[len - 1] == '\r')) {
        line[--len] = '\0';
    }
    return line;
}

static size_t split_tabs(char *line, char **parts, size_t capacity) {
    size_t count = 0;
    char *cursor = line;
    while (cursor && count < capacity) {
        parts[count++] = cursor;
        char *tab = strchr(cursor, '\t');
        if (!tab) break;
        *tab = '\0';
        cursor = tab + 1;
    }
    return count;
}

static int64_t parse_i64(const char *text, const char *label) {
    errno = 0;
    char *end = NULL;
    long long value = strtoll(text, &end, 10);
    if (errno || !end || *end != '\0') {
        fprintf(stderr, "pdrs-c: invalid %s: %s\n", label, text);
        exit(2);
    }
    return (int64_t)value;
}

static uint64_t parse_u64(const char *text, const char *label) {
    errno = 0;
    char *end = NULL;
    unsigned long long value = strtoull(text, &end, 10);
    if (errno || !end || *end != '\0') {
        fprintf(stderr, "pdrs-c: invalid %s: %s\n", label, text);
        exit(2);
    }
    return (uint64_t)value;
}

static void schema_init(Schema *schema) {
    memset(schema, 0, sizeof(*schema));
    schema->node_cap = INITIAL_NODE_CAP;
    schema->nodes = xcalloc(schema->node_cap, sizeof(Node));
}

static void schema_free(Schema *schema) {
    free(schema->name);
    free(schema->version);
    free(schema->root_name);
    for (size_t i = 0; i < schema->node_count; ++i) {
        Node *node = &schema->nodes[i];
        free(node->name);
        free(node->field);
        free(node->target_name);
        for (size_t j = 0; j < node->branch_count; ++j) {
            free(node->branches[j].value);
            free(node->branches[j].target_name);
        }
        free(node->branches);
    }
    free(schema->nodes);
    free(schema->counts);
    free(schema->states);
    memset(schema, 0, sizeof(*schema));
}

static Node *schema_add_node(Schema *schema) {
    if (schema->node_count == schema->node_cap) {
        schema->node_cap *= 2;
        schema->nodes = xrealloc(schema->nodes, schema->node_cap * sizeof(Node));
        memset(schema->nodes + schema->node_count, 0,
               (schema->node_cap - schema->node_count) * sizeof(Node));
    }
    Node *node = &schema->nodes[schema->node_count++];
    memset(node, 0, sizeof(*node));
    return node;
}

static size_t find_node(const Schema *schema, const char *name) {
    for (size_t i = 0; i < schema->node_count; ++i) {
        if (strcmp(schema->nodes[i].name, name) == 0) return i;
    }
    fprintf(stderr, "pdrs-c: missing target node %s\n", name);
    exit(2);
}

static void resolve_targets(Schema *schema) {
    schema->root = find_node(schema, schema->root_name);
    for (size_t i = 0; i < schema->node_count; ++i) {
        Node *node = &schema->nodes[i];
        if (node->type == NODE_CHOICE) {
            for (size_t j = 0; j < node->branch_count; ++j) {
                node->branches[j].target = find_node(schema, node->branches[j].target_name);
            }
        } else if (node->type == NODE_RANGE) {
            node->target = find_node(schema, node->target_name);
        }
    }
}

static uint64_t checked_add(uint64_t left, uint64_t right) {
    if (UINT64_MAX - left < right) die("domain cardinality exceeds uint64");
    return left + right;
}

static uint64_t checked_mul(uint64_t left, uint64_t right) {
    if (left != 0 && right > UINT64_MAX / left) die("domain cardinality exceeds uint64");
    return left * right;
}

static uint64_t compute_count(Schema *schema, size_t index, size_t depth) {
    if (depth > 100000) die("schema depth limit exceeded");
    if (schema->states[index] == 1) die("cycle detected");
    if (schema->states[index] == 2) return schema->counts[index];
    schema->states[index] = 1;
    if (depth > schema->max_depth) schema->max_depth = depth;
    Node *node = &schema->nodes[index];
    uint64_t total = 0;
    if (node->type == NODE_TERMINAL) {
        total = 1;
    } else if (node->type == NODE_CHOICE) {
        for (size_t i = 0; i < node->branch_count; ++i) {
            total = checked_add(total, compute_count(schema, node->branches[i].target, depth + 1));
        }
    } else {
        uint64_t width = (uint64_t)(node->stop - node->start) + 1u;
        total = checked_mul(width, compute_count(schema, node->target, depth + 1));
    }
    if (total == 0) die("empty domain");
    schema->counts[index] = total;
    schema->states[index] = 2;
    return total;
}

static Schema load_schema(const char *path) {
    FILE *handle = fopen(path, "r");
    if (!handle) {
        fprintf(stderr, "pdrs-c: cannot open %s\n", path);
        exit(2);
    }
    Schema schema;
    schema_init(&schema);
    char *line = NULL;
    size_t line_cap = 0;
    ssize_t length;
    bool saw_magic = false;
    while ((length = getline(&line, &line_cap, handle)) >= 0) {
        (void)length;
        trim_newline(line);
        if (line[0] == '\0' || line[0] == '#') continue;
        if (!saw_magic) {
            if (strcmp(line, "PDRS_IR_V1") != 0) die("invalid IR magic");
            saw_magic = true;
            continue;
        }
        char *parts[MAX_TOKENS_PER_LINE];
        size_t count = split_tabs(line, parts, MAX_TOKENS_PER_LINE);
        if (count < 2) die("malformed IR line");
        if (strcmp(parts[0], "name") == 0) {
            free(schema.name);
            schema.name = xstrdup(parts[1]);
        } else if (strcmp(parts[0], "version") == 0) {
            free(schema.version);
            schema.version = xstrdup(parts[1]);
        } else if (strcmp(parts[0], "root") == 0) {
            free(schema.root_name);
            schema.root_name = xstrdup(parts[1]);
        } else if (strcmp(parts[0], "node") == 0) {
            if (count < 3) die("malformed node line");
            Node *node = schema_add_node(&schema);
            if (strcmp(parts[1], "T") == 0) {
                if (count != 3) die("malformed terminal node");
                node->type = NODE_TERMINAL;
                node->name = xstrdup(parts[2]);
            } else if (strcmp(parts[1], "C") == 0) {
                if (count < 6) die("malformed choice node");
                node->type = NODE_CHOICE;
                node->name = xstrdup(parts[2]);
                node->field = xstrdup(parts[3]);
                uint64_t branch_count = parse_u64(parts[4], "branch count");
                if (branch_count > SIZE_MAX || count != 5 + 2 * (size_t)branch_count) {
                    die("choice branch count mismatch");
                }
                node->branch_count = (size_t)branch_count;
                node->branches = xcalloc(node->branch_count, sizeof(Branch));
                for (size_t i = 0; i < node->branch_count; ++i) {
                    node->branches[i].value = xstrdup(parts[5 + 2 * i]);
                    node->branches[i].target_name = xstrdup(parts[6 + 2 * i]);
                }
            } else if (strcmp(parts[1], "R") == 0) {
                if (count != 7) die("malformed range node");
                node->type = NODE_RANGE;
                node->name = xstrdup(parts[2]);
                node->field = xstrdup(parts[3]);
                node->start = parse_i64(parts[4], "range start");
                node->stop = parse_i64(parts[5], "range stop");
                if (node->stop < node->start) die("range stop is below start");
                node->target_name = xstrdup(parts[6]);
            } else {
                die("unknown node type");
            }
        } else {
            die("unknown IR record");
        }
    }
    free(line);
    fclose(handle);
    if (!saw_magic || !schema.name || !schema.version || !schema.root_name || schema.node_count == 0) {
        die("incomplete IR file");
    }
    resolve_targets(&schema);
    schema.counts = xcalloc(schema.node_count, sizeof(uint64_t));
    schema.states = xcalloc(schema.node_count, sizeof(unsigned char));
    (void)compute_count(&schema, schema.root, 0);
    for (size_t i = 0; i < schema.node_count; ++i) {
        if (schema.states[i] != 2) die("unreachable node detected");
    }
    return schema;
}

static int rank_value(const Schema *schema, const Token *tokens, size_t token_count, uint64_t *output) {
    size_t node_index = schema->root;
    size_t position = 0;
    uint64_t rank = 0;
    for (;;) {
        const Node *node = &schema->nodes[node_index];
        if (node->type == NODE_TERMINAL) {
            if (position != token_count) return -1;
            *output = rank;
            return 0;
        }
        if (position >= token_count) return -1;
        const Token *token = &tokens[position++];
        if (node->type == NODE_CHOICE) {
            if (token->is_int) return -1;
            uint64_t offset = 0;
            bool found = false;
            for (size_t i = 0; i < node->branch_count; ++i) {
                const Branch *branch = &node->branches[i];
                if (strcmp(token->str_value, branch->value) == 0) {
                    rank = checked_add(rank, offset);
                    node_index = branch->target;
                    found = true;
                    break;
                }
                offset = checked_add(offset, schema->counts[branch->target]);
            }
            if (!found) return -1;
        } else {
            if (!token->is_int || token->int_value < node->start || token->int_value > node->stop) return -1;
            uint64_t block = schema->counts[node->target];
            uint64_t local = (uint64_t)(token->int_value - node->start);
            rank = checked_add(rank, checked_mul(local, block));
            node_index = node->target;
        }
    }
}

static int unrank_value(const Schema *schema, uint64_t index, Token *tokens, size_t capacity, size_t *token_count) {
    if (index >= schema->counts[schema->root]) return -1;
    size_t node_index = schema->root;
    size_t length = 0;
    uint64_t remainder = index;
    for (;;) {
        const Node *node = &schema->nodes[node_index];
        if (node->type == NODE_TERMINAL) {
            if (remainder != 0) return -1;
            *token_count = length;
            return 0;
        }
        if (length >= capacity) return -1;
        if (node->type == NODE_CHOICE) {
            uint64_t offset = 0;
            bool found = false;
            for (size_t i = 0; i < node->branch_count; ++i) {
                const Branch *branch = &node->branches[i];
                uint64_t next = checked_add(offset, schema->counts[branch->target]);
                if (remainder < next) {
                    remainder -= offset;
                    tokens[length++] = (Token){.is_int = false, .int_value = 0, .str_value = branch->value};
                    node_index = branch->target;
                    found = true;
                    break;
                }
                offset = next;
            }
            if (!found) return -1;
        } else {
            uint64_t block = schema->counts[node->target];
            uint64_t local = remainder / block;
            remainder %= block;
            int64_t value = node->start + (int64_t)local;
            if (value > node->stop) return -1;
            tokens[length++] = (Token){.is_int = true, .int_value = value, .str_value = NULL};
            node_index = node->target;
        }
    }
}

static void print_tokens(FILE *out, const Token *tokens, size_t count) {
    for (size_t i = 0; i < count; ++i) {
        if (i) fputc('|', out);
        if (tokens[i].is_int) {
            fprintf(out, "I:%" PRId64, tokens[i].int_value);
        } else {
            fprintf(out, "S:%s", tokens[i].str_value);
        }
    }
}

static uint64_t monotonic_ns(void) {
    struct timespec ts;
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) die("clock_gettime failed");
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static int command_verify(const char *path) {
    Schema schema = load_schema(path);
    uint64_t count = schema.counts[schema.root];
    Token *tokens = xcalloc(schema.node_count + 1, sizeof(Token));
    uint64_t failures = 0;
    for (uint64_t index = 0; index < count; ++index) {
        size_t length = 0;
        uint64_t reconstructed = UINT64_MAX;
        if (unrank_value(&schema, index, tokens, schema.node_count + 1, &length) != 0 ||
            rank_value(&schema, tokens, length, &reconstructed) != 0 || reconstructed != index) {
            ++failures;
        }
    }
    printf("{\"language\":\"c\",\"schema\":\"%s\",\"count\":%" PRIu64
           ",\"checked\":%" PRIu64 ",\"failures\":%" PRIu64 "}\n",
           schema.name, count, count, failures);
    free(tokens);
    schema_free(&schema);
    return failures == 0 ? 0 : 1;
}

static int command_vectors(const char *path, const char *ranks_path) {
    Schema schema = load_schema(path);
    FILE *ranks = fopen(ranks_path, "r");
    if (!ranks) die("cannot open ranks file");
    Token *tokens = xcalloc(schema.node_count + 1, sizeof(Token));
    char line[128];
    while (fgets(line, sizeof(line), ranks)) {
        trim_newline(line);
        if (!line[0]) continue;
        uint64_t index = parse_u64(line, "rank");
        size_t length = 0;
        if (unrank_value(&schema, index, tokens, schema.node_count + 1, &length) != 0) die("invalid vector rank");
        printf("%" PRIu64 "\t", index);
        print_tokens(stdout, tokens, length);
        fputc('\n', stdout);
    }
    fclose(ranks);
    free(tokens);
    schema_free(&schema);
    return 0;
}

static int command_bench(const char *path, uint64_t iterations) {
    Schema schema = load_schema(path);
    uint64_t count = schema.counts[schema.root];
    size_t sample_count = count < 4096 ? (size_t)count : 4096;
    TokenVec *samples = xcalloc(sample_count, sizeof(TokenVec));
    uint64_t state = 0x9e3779b97f4a7c15ull;
    for (size_t i = 0; i < sample_count; ++i) {
        state = state * 6364136223846793005ull + 1442695040888963407ull;
        uint64_t index = state % count;
        Token *items = xcalloc(schema.node_count + 1, sizeof(Token));
        size_t length = 0;
        if (unrank_value(&schema, index, items, schema.node_count + 1, &length) != 0) die("benchmark unrank setup failed");
        samples[i].items = items;
        samples[i].len = length;
    }
    volatile uint64_t sink = 0;
    uint64_t started = monotonic_ns();
    for (uint64_t i = 0; i < iterations; ++i) {
        const TokenVec *sample = &samples[i % sample_count];
        uint64_t rank = 0;
        if (rank_value(&schema, sample->items, sample->len, &rank) != 0) die("benchmark rank failed");
        sink ^= rank;
    }
    uint64_t rank_elapsed = monotonic_ns() - started;
    Token *scratch = xcalloc(schema.node_count + 1, sizeof(Token));
    started = monotonic_ns();
    for (uint64_t i = 0; i < iterations; ++i) {
        size_t length = 0;
        uint64_t index = (i * 11400714819323198485ull) % count;
        if (unrank_value(&schema, index, scratch, schema.node_count + 1, &length) != 0) die("benchmark unrank failed");
        sink ^= (uint64_t)length;
    }
    uint64_t unrank_elapsed = monotonic_ns() - started;
    double rank_ns = (double)rank_elapsed / (double)iterations;
    double unrank_ns = (double)unrank_elapsed / (double)iterations;
    printf("{\"language\":\"c\",\"schema\":\"%s\",\"count\":%" PRIu64
           ",\"iterations\":%" PRIu64 ",\"rank_ns\":%.6f,\"unrank_ns\":%.6f,\"sink\":%" PRIu64 "}\n",
           schema.name, count, iterations, rank_ns, unrank_ns, sink);
    free(scratch);
    for (size_t i = 0; i < sample_count; ++i) free(samples[i].items);
    free(samples);
    schema_free(&schema);
    return 0;
}

static void usage(void) {
    fprintf(stderr,
            "usage:\n"
            "  pdrs-c verify SCHEMA.pdrs\n"
            "  pdrs-c vectors SCHEMA.pdrs RANKS.txt\n"
            "  pdrs-c bench SCHEMA.pdrs ITERATIONS\n");
}

int main(int argc, char **argv) {
    if (argc < 3) {
        usage();
        return 2;
    }
    if (strcmp(argv[1], "verify") == 0 && argc == 3) return command_verify(argv[2]);
    if (strcmp(argv[1], "vectors") == 0 && argc == 4) return command_vectors(argv[2], argv[3]);
    if (strcmp(argv[1], "bench") == 0 && argc == 4) return command_bench(argv[2], parse_u64(argv[3], "iterations"));
    usage();
    return 2;
}
